from dataclasses import dataclass


@dataclass(frozen=True)
class EngineDefinition:
    id: str
    label: str
    default_tone: str
    visual_types: tuple[str, ...]
    requires_fact_review: bool = True


ENGINES = {
    "football": EngineDefinition(
        id="football",
        label="Football Engine",
        default_tone="informativo, direto e energético",
        visual_types=("headline", "stat", "image", "quote"),
    ),
    "geo": EngineDefinition(
        id="geo",
        label="Geo Engine",
        default_tone="curioso, claro e visual",
        visual_types=("headline", "map", "stat", "image"),
    ),
    "music": EngineDefinition(
        id="music",
        label="Music Engine",
        default_tone="cultural, autoral e envolvente",
        visual_types=("headline", "image", "quote", "stat"),
    ),
}


def get_engine(engine_id: str) -> EngineDefinition:
    try:
        return ENGINES[engine_id]
    except KeyError as exc:
        raise ValueError(f"Unknown engine: {engine_id}") from exc
