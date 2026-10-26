"""M4.D additions: closed visual materials, exact approved text and bundled fonts."""

import json

import pytest
from pydantic import ValidationError

from apps.api.motion_contracts.fonts import FONTS, font_source, layout_text, metrics
from apps.api.motion_contracts.models import Gradient, MotionRecipe, MotionScene, ShotText
from apps.api.motion_contracts.registry import load_recipe, recipe_digest
from apps.api.motion_contracts.validation import shot_text
from scripts.motion_recipes_v12 import build_v12


@pytest.fixture(autouse=True)
def clean_database():
    # Pure contract tests; no application DB or renderer is started here.
    yield


@pytest.mark.parametrize(
    "label,recipe_id",
    [
        ("sports", "sports.depth-impact"),
        ("music", "music.orbital-sleeve"),
        ("geo", "geo.route-explainer"),
    ],
)
def test_new_recipes_reproducible_and_older_hashes_preserved(label, recipe_id):
    for version in ("1.0.0", "1.1.0", "1.2.0"):
        recipe = load_recipe(recipe_id, version)
        assert recipe.sha256 == recipe_digest(recipe)
    assert build_v12(label).sha256 == load_recipe(recipe_id, "1.2.0").sha256


def gradient():
    return {
        "kind": "linear",
        "stops": [
            {"offset": 0, "color": {"index": 0}},
            {"offset": 1, "color": {"index": 1}},
        ],
    }


@pytest.mark.parametrize(
    "update",
    [
        {"kind": "url"},
        {"href": "https://example.com/paint.svg"},
        {"radius": 1000},
        {"start": [-1, 0]},
        {"radius": float("nan")},
    ],
)
def test_gradient_rejects_external_content_nonfinite_and_unbounded_effects(update):
    with pytest.raises(ValidationError):
        Gradient.model_validate({**gradient(), **update})


def test_gradient_stop_and_glow_budgets():
    data = gradient()
    data["stops"][1]["offset"] = 0
    with pytest.raises(ValidationError, match="strictly ordered"):
        Gradient.model_validate(data)
    data = gradient()
    data["stops"] = data["stops"] * 5
    with pytest.raises(ValidationError):
        Gradient.model_validate(data)
    nodes = [
        {
            "id": f"s-{i}",
            "type": "shape",
            "params": {
                "geometry": {"kind": "rect", "width": 100, "height": 100},
                "fill_gradient": gradient(),
                "glow": 4,
            },
        }
        for i in range(9)
    ]
    with pytest.raises(ValidationError, match="[Gg]low"):
        MotionScene.model_validate({"schema_version": "motion_scene_v1", "nodes": nodes})


def test_selected_lines_are_exact_approved_content_not_generated_text():
    text = "Órbita\nESTUDO SONORO"
    binding = ShotText(kind="shot_field", field="on_screen_text", line_index=1)
    assert shot_text(binding, text) == "ESTUDO SONORO"
    assert shot_text(binding.model_copy(update={"line_index": None}), text) == text
    with pytest.raises(ValueError):
        shot_text(binding, "No second approved line")
    with pytest.raises(ValueError):
        shot_text(binding, "First\n")
    with pytest.raises(ValidationError):
        ShotText(kind="shot_field", field="on_screen_text", line_index=1, replacement="Invented")


@pytest.mark.parametrize("family", list(FONTS))
def test_font_metrics_and_tracking_use_exact_bundled_font(family):
    _, base = layout_text("Órbita", 64, 900, 1, family)
    _, tracked = layout_text("Órbita", 64, 900, 1, family, 3)
    assert tracked["widths"][0] == pytest.approx(base["widths"][0] + 6 * 3)
    assert tracked["font_sha256"] == metrics(font_source(family).read_text(encoding="utf-8"))[1]
    with pytest.raises(ValueError, match="TEXT_OVERFLOW"):
        layout_text("Órbita", 64, base["widths"][0] + 1, 1, family, 3)
    with pytest.raises(ValueError, match="UNSUPPORTED_GLYPH"):
        layout_text("🦄", 64, 900, 1, family)


def test_closed_font_registry_and_provenance():
    with pytest.raises(ValueError, match="FONT_UNSUPPORTED"):
        font_source("https://remote.example/font.ttf")
    source = font_source("Space Grotesk").parent
    manifest = json.loads((source / "motion-font-provenance.json").read_text())
    assert manifest
    for family in ("Space Grotesk", "IBM Plex Sans"):
        license_file = font_source(family).with_name(FONTS[family] + "-OFL.txt")
        assert "OPEN FONT LICENSE" in license_file.read_text()


def test_gradients_change_recipe_identity_but_dont_add_executable_fields():
    recipe = build_v12("music")
    altered = recipe.model_dump()
    shape = next(n for n in altered["scenes"][0]["graph"]["nodes"] if n["type"] == "shape")
    shape["params"]["fill_gradient"]["stops"][0]["opacity"] = 0.5
    assert recipe_digest(MotionRecipe.model_validate(altered)) != recipe.sha256
