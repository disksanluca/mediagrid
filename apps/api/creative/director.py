"""Deterministic direction reference. It creates no facts and calls no model."""

from .contracts import CreativeBrief, CreativeDirection, CreativeDirectionSet, CreativeDNA


def propose_directions(brief: CreativeBrief, dna: CreativeDNA) -> CreativeDirectionSet:
    subject = brief.topic.strip()
    audience = brief.audience.strip()
    objective = brief.objective.strip()
    factual = brief.factual_mode == "FACT_CHECK_REQUIRED"
    concepts = (
        (
            "evidence-led", "Editorial de Evidências" if factual else "Editorial Narrativo",
            "Revelar o assunto por camadas, com contexto visual antes da conclusão.",
            "Contexto → pergunta → síntese", "hybrid", "Hierarquia editorial e espaço negativo",
            "Revelação de texto por blocos e cortes motivados", "MEDIUM",
        ),
        (
            "timeline", "Linha do Tempo" if factual else "Progressão Visual",
            "Organizar a narrativa em uma sequência clara de marcos e transições.",
            "Início → desenvolvimento → consequência", "dynamic",
            "Eixo temporal e cartões de apoio", "Transições lineares e marcadores discretos",
            "MEDIUM",
        ),
        (
            "questions", "Perguntas e Respostas",
            "Conduzir o público por perguntas curtas e respostas verificáveis.",
            "Dúvida → análise → conclusão", "slow",
            "Quadros de pergunta e resposta com contraste",
            "Pausas, ênfase tipográfica e dissolvência",
            "LOW",
        ),
    )
    directions = []
    for identifier, title, thesis, arc, rhythm, composition, motion, complexity in concepts:
        directions.append(CreativeDirection(
            id=identifier, title=title, thesis=thesis,
            rationale=(f"Proposta para '{subject}', voltada a {audience}. "
                       f"Objetivo declarado: {objective}. "
                       "Alegações dependem das fontes e da revisão humana."),
            emotional_arc=arc, rhythm=rhythm, typography=dna.font_display,
            composition=composition, motion_language=motion,
            palette=dna.palette, estimated_complexity=complexity,
        ))
    return CreativeDirectionSet(directions=directions)
