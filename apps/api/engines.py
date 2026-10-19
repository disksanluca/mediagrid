from dataclasses import dataclass


@dataclass(frozen=True)
class EngineDefinition:
    id: str
    label: str
    default_tone: str
    visual_types: tuple[str, ...]
    scene_guidance: tuple[str, str, str]
    review_checks: tuple[str, ...]
    requires_fact_review: bool = True


ENGINES = {
    "football": EngineDefinition(
        id="football",
        label="Football Engine",
        default_tone="informativo, direto e energético",
        visual_types=("headline", "stat", "image", "quote"),
        scene_guidance=(
            "Contextualize a partida, a temporada e as equipes.",
            "Confirme placar, data e estatísticas em fontes primárias.",
            "Explique o impacto esportivo sem especular sobre atletas.",
        ),
        review_checks=(
            "Verificar placares, datas e estatísticas",
            "Confirmar direitos de imagens e escudos",
        ),
    ),
    "geo": EngineDefinition(
        id="geo",
        label="Geo Engine",
        default_tone="curioso, claro e visual",
        visual_types=("headline", "map", "stat", "image"),
        scene_guidance=(
            "Localize o lugar e a escala do fenômeno.",
            "Use mapas e dados geográficos com fonte e data.",
            "Explique limites dos dados e impactos locais.",
        ),
        review_checks=("Conferir mapa, fronteiras e escala", "Citar fontes e datas dos dados"),
    ),
    "music": EngineDefinition(
        id="music",
        label="Music Engine",
        default_tone="cultural, autoral e envolvente",
        visual_types=("headline", "image", "quote", "stat"),
        scene_guidance=(
            "Apresente artista, obra e contexto cultural.",
            "Confirme créditos, lançamentos e declarações.",
            "Explique a relevância musical sem reproduzir material protegido.",
        ),
        review_checks=("Conferir créditos e datas", "Confirmar direitos de áudio, capa e trechos"),
    ),
    "clips": EngineDefinition(
        id="clips",
        label="Clips Engine",
        default_tone="ágil, contextual e autoral",
        visual_types=("headline", "image", "quote", "stat"),
        scene_guidance=(
            "Identifique a origem e o contexto do clipe.",
            "Explique o trecho com informação verificável.",
            "Adicione comentário ou análise original.",
        ),
        review_checks=(
            "Confirmar licença do clipe e do áudio",
            "Verificar atribuição e contexto original",
        ),
    ),
    "politics": EngineDefinition(
        id="politics",
        label="Politics Engine",
        default_tone="neutro, preciso e contextual",
        visual_types=("headline", "quote", "stat", "image"),
        scene_guidance=(
            "Identifique o fato, local e data.",
            "Separe declarações de fatos e confira documentos primários.",
            "Apresente contexto e posições relevantes com atribuição.",
        ),
        review_checks=(
            "Conferir fontes primárias e datas",
            "Revisão humana de alegações e equilíbrio editorial",
        ),
    ),
    "trends": EngineDefinition(
        id="trends",
        label="Trends Engine",
        default_tone="curioso, claro e com contexto",
        visual_types=("headline", "stat", "image", "quote"),
        scene_guidance=(
            "Defina a tendência e o período observado.",
            "Confirme os sinais e sua origem antes de inferir crescimento.",
            "Explique o alcance e as limitações da tendência.",
        ),
        review_checks=(
            "Confirmar origem e período dos sinais",
            "Evitar apresentar amostra como tendência geral",
        ),
    ),
}


def get_engine(engine_id: str) -> EngineDefinition:
    try:
        return ENGINES[engine_id]
    except KeyError as exc:
        raise ValueError(f"Unknown engine: {engine_id}") from exc
