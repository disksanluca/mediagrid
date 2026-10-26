"""Local versioned data-only registry. Never imports/evaluates a recipe as code."""

from pathlib import Path
from typing import Literal

from pydantic import Field, TypeAdapter

from .canonical import MAX_JSON_BYTES, canonical_bytes, contract_sha256, read_json
from .models import Contract, Identifier, MotionComposition, MotionRecipe, RecipeRef, Version

REGISTRY_ROOT = Path(__file__).resolve().parents[3] / "contracts" / "motion" / "recipes"


class RegistryIndex(Contract):
    schema_version: Literal["motion_registry_v1"]
    recipes: list[RecipeRef] = Field(min_length=1, max_length=64)


def bounded_read(path: Path, root: Path) -> bytes:
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Recipe path escapes local registry")
    with path.open("rb") as stream:
        data = stream.read(MAX_JSON_BYTES+1)
    if len(data) > MAX_JSON_BYTES:
        raise ValueError("Recipe exceeds 2 MiB")
    return data


def recipe_digest(recipe: MotionRecipe) -> str:
    return contract_sha256(recipe.model_dump(mode="json", exclude={"sha256"}))


def verify_recipe(recipe: MotionRecipe) -> MotionRecipe:
    # Revalidation also covers mutated containers / model_copy(update=...) inputs.
    recipe = MotionRecipe.model_validate(recipe.model_dump(mode="json"))
    if recipe_digest(recipe) != recipe.sha256:
        raise ValueError("Recipe content hash mismatch")
    return recipe


def load_recipe(recipe_id: str, version: str, *, root: Path = REGISTRY_ROOT) -> MotionRecipe:
    TypeAdapter(Identifier).validate_python(recipe_id, strict=True)
    TypeAdapter(Version).validate_python(version, strict=True)
    index = RegistryIndex.model_validate(read_json(bounded_read(root / "index.json", root)))
    keys = [(r.id, r.version) for r in index.recipes]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate recipe version in registry")
    matches = [r for r in index.recipes if (r.id, r.version) == (recipe_id, version)]
    if len(matches) != 1:
        raise ValueError("Recipe version is not registered")
    recipe = verify_recipe(MotionRecipe.model_validate(read_json(
        bounded_read(root / f"{recipe_id}.{version}.json", root)
    )))
    if (recipe.id, recipe.version, recipe.sha256) != (
        matches[0].id, matches[0].version, matches[0].sha256
    ):
        raise ValueError("Recipe identity/hash differs from registry")
    return recipe


def verify_recipe_binding(composition: MotionComposition, recipe: MotionRecipe):
    recipe = verify_recipe(recipe)
    ref = composition.recipe
    if (ref.id, ref.version, ref.sha256) != (recipe.id, recipe.version, recipe.sha256):
        raise ValueError("Composition recipe identity/hash mismatch")
    if composition.expected.canvas != recipe.canvas or composition.expected.duration_ms != sum(
        s.required_duration_ms for s in recipe.scenes
    ):
        raise ValueError("Composition violates recipe canvas/duration assertions")
    if {k: v.kind for k, v in composition.asset_bindings.items()} != recipe.asset_slots:
        raise ValueError("Composition asset slots differ from recipe")
    if len(composition.scenes) != len(recipe.scenes) or any(
        canonical_bytes(scene.graph) != canonical_bytes(template.graph)
        for scene, template in zip(composition.scenes, recipe.scenes, strict=True)
    ):
        raise ValueError("Expanded graph differs from registered recipe")
