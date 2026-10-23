"""Build an editable motion ad exclusively from the creator's supplied copy."""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from .edl_v2 import EDLV2, TimelineItem, TimelineTrack, from_legacy, scene_projection
from .models import Channel, Project, ProjectRevision, ProjectStatus
from .schemas import ContentPlan, Scene
from .services import record_event


class MotionAdCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str
    format: Literal["vertical", "horizontal"] = "vertical"
    product_name: str = Field(min_length=2, max_length=60)
    audience: str = Field(min_length=5, max_length=100)
    hook: str = Field(min_length=12, max_length=78)
    problem: str = Field(min_length=12, max_length=78)
    benefit: str = Field(min_length=12, max_length=78)
    call_to_action: str = Field(min_length=5, max_length=60)
    brand_color: str = Field(default="#c4d4ef", pattern=r"^#[0-9a-fA-F]{6}$")

    @model_validator(mode="after")
    def no_blank_copy(self) -> "MotionAdCreate":
        minimum = {
            "product_name": 2, "audience": 5, "hook": 12, "problem": 12,
            "benefit": 12, "call_to_action": 5,
        }
        for field, length in minimum.items():
            value = getattr(self, field).strip()
            if len(value) < length:
                raise ValueError(f"Preencha {field} com pelo menos {length} caracteres")
            setattr(self, field, value)
        if len({self.hook.casefold(), self.problem.casefold(), self.benefit.casefold(),
                self.call_to_action.casefold()}) != 4:
            raise ValueError("Cada etapa precisa de uma mensagem diferente")
        return self


def _scene(scene_id: str, copy: str, visual_type: str, transition: str) -> Scene:
    duration = max(4, min(8, round(len(copy.split()) / 2.4 + 2)))
    return Scene(
        id=scene_id, duration_seconds=duration, narration=copy.strip(),
        visual_type=visual_type, visual_query="arte tipográfica original",
        on_screen_text=copy.strip(), transition=transition,
    )


def _motion_card(card_id: str, start_ms: int, duration_ms: int,
                 label: str, text: str, body: str, color: str) -> TimelineItem:
    return TimelineItem(
        id=card_id, start_ms=start_ms, duration_ms=duration_ms, z_index=15,
        preset="motion_card_v1", params={
            "label": label, "text": text, "body": body, "color": color,
            "layout": "stack",
            "keyframes": [
                {"at_ms": 0, "x": .5, "y": .5, "opacity": 0, "scale": .85},
                {"at_ms": 500, "x": .5, "y": .5, "opacity": 1, "scale": 1},
                {"at_ms": duration_ms, "x": .5, "y": .5, "opacity": 1, "scale": 1},
            ],
        },
    )


def create_motion_ad(db: Session, channel: Channel, brief: MotionAdCreate) -> Project:
    project = Project(
        channel_id=channel.id, title=f"{brief.product_name.strip()} · Motion Ad",
        topic=f"Anúncio de {brief.product_name.strip()} para {brief.audience.strip()}",
        content_type="motion_ad", format=brief.format,
        status=ProjectStatus.SCRIPTED.value,
    )
    db.add(project)
    db.flush()
    scenes = [
        _scene("ad-hook", brief.hook, "headline", "impact"),
        _scene("ad-problem", brief.problem, "quote", "slide"),
        _scene("ad-benefit", brief.benefit, "image", "zoom"),
        _scene("ad-cta", brief.call_to_action, "outro", "fade"),
    ]
    plan = ContentPlan(
        project_id=project.id, engine=channel.default_engine, origin="BRIEF_BASED",
        hook=brief.hook.strip(),
        angle=f"Anúncio dirigido a {brief.audience.strip()}; texto fornecido pelo criador.",
        target_duration_seconds=round(sum(scene.duration_seconds for scene in scenes)),
        scenes=scenes, requires_fact_review=True,
        review_checks=[
            "Comprovar as alegações do problema e benefício antes da entrega",
            "Conferir direitos de marca, voz, trilha e mídia adicionada",
            "Revisar a oferta e a chamada para ação no vídeo final",
        ],
    )
    brief_snapshot = brief.model_dump()
    encoded_brief = json.dumps(
        brief_snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    brief_sha256 = hashlib.sha256(encoded_brief.encode("utf-8")).hexdigest()
    project.plan = {**plan.model_dump(), "initial_motion_ad_brief": brief_snapshot,
                    "initial_motion_ad_brief_sha256": brief_sha256}
    project.script = {"language": channel.language,
                      "segments": [scene.narration for scene in scenes]}
    project.edl = {
        "version": 1, "format": brief.format,
        "tracks": {
            "video": [{"scene_id": scene.id, "duration": scene.duration_seconds,
                       "visual_type": scene.visual_type, "transition": scene.transition}
                      for scene in scenes],
            "audio": [{"scene_id": scene.id, "text": scene.narration} for scene in scenes],
            "captions": [{"scene_id": scene.id, "text": scene.on_screen_text}
                         for scene in scenes],
        },
    }
    base = from_legacy(project.edl, project.plan)
    benefit_start = round(sum(scene.duration_seconds for scene in scenes[:2]) * 1000)
    cta_start = benefit_start + round(scenes[2].duration_seconds * 1000)
    cards = TimelineTrack(id="ad-cards", kind="caption", items=[
        _motion_card(
            "ad-card-benefit", benefit_start, round(scenes[2].duration_seconds * 1000),
            "PROPOSTA", brief.product_name.strip(), brief.benefit.strip(), brief.brand_color,
        ),
        _motion_card(
            "ad-card-cta", cta_start, round(scenes[3].duration_seconds * 1000),
            "PRÓXIMO PASSO", brief.call_to_action.strip(),
            brief.product_name.strip(), brief.brand_color,
        ),
    ])
    edl = EDLV2.model_validate({
        **base.model_dump(),
        "tracks": [*[track.model_dump() for track in base.tracks], cards.model_dump()],
    })
    project.edl = scene_projection(edl, brief.format)[0]
    encoded_edl = json.dumps(
        edl.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    db.add(ProjectRevision(
        project_id=project.id, revision=edl.revision, edl=edl.model_dump(),
        sha256=hashlib.sha256(encoded_edl.encode("utf-8")).hexdigest(),
    ))
    record_event(db, "MOTION_AD_BRIEF_CREATED", "project", project.id, after={
        "brief_sha256": brief_sha256,
        "scene_ids": [scene.id for scene in scenes],
        "format": brief.format,
        "factual_review": "REQUIRED",
    })
    return project
