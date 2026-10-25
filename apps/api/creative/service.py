"""SQLAlchemy-backed creative revisions and derived review validity."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    Asset,
    Channel,
    CreativeBriefRevision,
    CreativeDirectionSet,
    CreativeDNARevision,
    CreativeReview,
    CreativeStoryboardRevision,
    KnowledgeClaim,
    Project,
    ProjectRevision,
)
from ..services import record_event
from .contracts import (
    CreativeBrief,
    CreativeDecisionWrite,
    CreativeDirectionsWrite,
    CreativeDNA,
    CreativeStoryboard,
    CreativeStoryboardWrite,
)
from .director import propose_directions
from .hashing import content_sha256


def channel_for(db: Session, channel_id: str) -> Channel:
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(404, "Channel not found")
    return channel


def project_for(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


def latest(db: Session, model: type, owner_id: str):
    owner = model.channel_id if model is CreativeDNARevision else model.project_id
    return db.scalar(
        select(model).where(owner == owner_id).order_by(model.revision.desc()).limit(1)
    )


def require_revision(current, expected: int) -> None:
    actual = current.revision if current else 0
    if expected != actual:
        raise HTTPException(409, {
            "code": "CREATIVE_REVISION_CONFLICT", "current_revision": actual,
        })


def serialized(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "revision": row.revision,
        "sha256": row.sha256,
        "content": row.payload,
        "created_at": row.created_at.isoformat(),
    }


def commit_revision(db: Session, row, event_type: str, entity_type: str,
                    entity_id: str) -> dict[str, Any]:
    db.add(row)
    try:
        db.flush()
        record_event(db, event_type, entity_type, entity_id,
                     after={"revision": row.revision, "sha256": row.sha256})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Creative revision changed; reload before saving") from exc
    return serialized(row)


def validate_asset_ids(db: Session, asset_ids: set[str]) -> None:
    for asset_id in asset_ids:
        if db.get(Asset, asset_id) is None:
            raise HTTPException(422, f"Unknown asset: {asset_id}")


def current_project_claims(db: Session, project_id: str) -> list[KnowledgeClaim]:
    return list(db.scalars(select(KnowledgeClaim).where(
        KnowledgeClaim.project_id == project_id,
        KnowledgeClaim.status != "REMOVED",
    ).order_by(KnowledgeClaim.created_at, KnowledgeClaim.id)))


def save_dna(db: Session, channel_id: str, expected_revision: int,
             content: CreativeDNA) -> dict:
    channel_for(db, channel_id)
    current = latest(db, CreativeDNARevision, channel_id)
    require_revision(current, expected_revision)
    row = CreativeDNARevision(
        channel_id=channel_id, revision=expected_revision + 1,
        payload=content.model_dump(mode="json"), sha256=content_sha256(content),
    )
    return commit_revision(db, row, "CREATIVE_DNA_REVISION_CREATED", "channel", channel_id)


def save_brief(db: Session, project_id: str, expected_revision: int,
               content: CreativeBrief) -> dict:
    project = project_for(db, project_id)
    if content.format != project.format:
        raise HTTPException(422, "Creative brief format must match the project")
    validate_asset_ids(db, set(content.asset_ids))
    current = latest(db, CreativeBriefRevision, project_id)
    require_revision(current, expected_revision)
    row = CreativeBriefRevision(
        project_id=project_id, revision=expected_revision + 1,
        payload=content.model_dump(mode="json"), sha256=content_sha256(content),
    )
    return commit_revision(db, row, "CREATIVE_BRIEF_REVISION_CREATED", "project", project_id)


def direction_status(db: Session, project: Project, row: CreativeDirectionSet) -> str:
    brief = latest(db, CreativeBriefRevision, project.id)
    dna = latest(db, CreativeDNARevision, project.channel_id)
    if not brief or not dna or row.brief_sha256 != brief.sha256 or row.dna_sha256 != dna.sha256:
        return "STALE"
    return "CURRENT"


def directions_read(db: Session, project: Project, row: CreativeDirectionSet) -> dict:
    return {**serialized(row), "origin": row.origin,
            "brief_sha256": row.brief_sha256, "dna_sha256": row.dna_sha256,
            "status": direction_status(db, project, row)}


def generate_directions(db: Session, project_id: str,
                        request: CreativeDirectionsWrite) -> dict:
    project = project_for(db, project_id)
    brief = latest(db, CreativeBriefRevision, project_id)
    dna = latest(db, CreativeDNARevision, project.channel_id)
    if brief is None or dna is None:
        raise HTTPException(409, "Save a creative brief and channel DNA first")
    require_revision(brief, request.expected_brief_revision)
    require_revision(dna, request.expected_dna_revision)
    current = latest(db, CreativeDirectionSet, project_id)
    require_revision(current, request.expected_revision)
    if current and direction_status(db, project, current) == "CURRENT":
        return directions_read(db, project, current)
    directions = propose_directions(
        CreativeBrief.model_validate(brief.payload), CreativeDNA.model_validate(dna.payload)
    )
    row = CreativeDirectionSet(
        project_id=project_id, revision=request.expected_revision + 1,
        brief_sha256=brief.sha256, dna_sha256=dna.sha256,
        origin="deterministic_reference", payload=directions.model_dump(mode="json"),
        sha256=content_sha256(directions),
    )
    commit_revision(db, row, "CREATIVE_DIRECTIONS_GENERATED", "project", project_id)
    return directions_read(db, project, row)


def storyboard_read(db: Session, project: Project, row: CreativeStoryboardRevision) -> dict:
    directions = latest(db, CreativeDirectionSet, project.id)
    valid = (directions is not None and row.direction_set_id == directions.id
             and direction_status(db, project, directions) == "CURRENT")
    return {**serialized(row), "direction_set_id": row.direction_set_id,
            "status": "CURRENT" if valid else "STALE"}


def save_storyboard(db: Session, project_id: str,
                    request: CreativeStoryboardWrite) -> dict:
    project = project_for(db, project_id)
    brief = latest(db, CreativeBriefRevision, project_id)
    directions = latest(db, CreativeDirectionSet, project_id)
    if (brief is None or directions is None
            or direction_status(db, project, directions) != "CURRENT"):
        raise HTTPException(409, "DIRECTIONS_STALE: regenerate directions first")
    require_revision(directions, request.expected_direction_revision)
    content: CreativeStoryboard = request.content
    brief_data = CreativeBrief.model_validate(brief.payload)
    if content.duration_ms != brief_data.duration_ms or content.fps != brief_data.fps:
        raise HTTPException(422, "Storyboard duration and fps must match the brief")
    if content.direction_id not in {
        direction["id"] for direction in directions.payload["directions"]
    }:
        raise HTTPException(422, "Select a current creative direction")
    shot_asset_ids = {item for shot in content.shots for item in shot.asset_ids}
    if not shot_asset_ids.issubset(set(brief_data.asset_ids)):
        raise HTTPException(422, "Add storyboard assets to the brief first")
    validate_asset_ids(db, shot_asset_ids)
    claim_ids = {item for shot in content.shots for item in shot.claim_ids}
    claims = {claim.id for claim in current_project_claims(db, project_id)}
    if not claim_ids.issubset(claims):
        raise HTTPException(422, "Storyboard references an unknown project claim")
    current = latest(db, CreativeStoryboardRevision, project_id)
    require_revision(current, request.expected_revision)
    row = CreativeStoryboardRevision(
        project_id=project_id, direction_set_id=directions.id,
        revision=request.expected_revision + 1, payload=content.model_dump(mode="json"),
        sha256=content_sha256(content),
    )
    commit_revision(db, row, "CREATIVE_STORYBOARD_REVISION_CREATED", "project", project_id)
    return storyboard_read(db, project, row)


def review_snapshot(db: Session, project: Project, board: CreativeStoryboardRevision,
                    ) -> tuple[str, list[str]]:
    """Recompute approval dependencies from current rows, including legacy project state."""
    brief = latest(db, CreativeBriefRevision, project.id)
    dna = latest(db, CreativeDNARevision, project.channel_id)
    directions = latest(db, CreativeDirectionSet, project.id)
    blockers: list[str] = []
    if not brief or not dna or not directions:
        blockers.append("Creative brief, DNA or directions are missing")
    elif (board.direction_set_id != directions.id
          or direction_status(db, project, directions) != "CURRENT"):
        blockers.append("DIRECTIONS_STALE")
    asset_ids = set(brief.payload.get("asset_ids", [])) if brief else set()
    asset_ids.update(item for shot in board.payload["shots"] for item in shot["asset_ids"])
    assets = []
    for asset_id in sorted(asset_ids):
        asset = db.get(Asset, asset_id)
        if asset is None:
            blockers.append(f"Asset {asset_id} is missing")
            assets.append({"id": asset_id, "missing": True})
            continue
        assets.append({"id": asset.id, "sha256": asset.sha256,
                       "rights_status": asset.rights_status,
                       "license_name": asset.license_name,
                       "commercial_use": asset.commercial_use,
                       "source_url": asset.source_url, "creator": asset.creator})
        if (asset.rights_status not in {"OWNED", "LICENSED"} or not asset.commercial_use
                or asset.rights_status == "LICENSED" and not asset.license_name):
            blockers.append(f"RIGHTS_BLOCKED: {asset_id}")
    claims = current_project_claims(db, project.id)
    claim_ids = {claim.id for claim in claims}
    for shot in board.payload["shots"]:
        if not set(shot["claim_ids"]).issubset(claim_ids):
            blockers.append(f"Shot {shot['id']} has a removed or missing claim")
    if any(claim.status != "APPROVED" for claim in claims):
        blockers.append("Factual claims need individual approval")
    if brief:
        brief_data = CreativeBrief.model_validate(brief.payload)
        if brief_data.format != project.format:
            blockers.append("Creative brief format differs from the project")
        if brief_data.factual_mode == "FACT_CHECK_REQUIRED" and (
            not brief_data.sources or any(not source.fact_reviewed for source in brief_data.sources)
        ):
            blockers.append("Factual brief needs reviewed sources")
    edl_revision = db.scalar(select(ProjectRevision).where(
        ProjectRevision.project_id == project.id
    ).order_by(ProjectRevision.revision.desc()).limit(1))
    snapshot = {
        "board": {"revision": board.revision, "sha256": board.sha256},
        "direction": {"id": directions.id, "revision": directions.revision,
                      "sha256": directions.sha256} if directions else None,
        "brief": {"revision": brief.revision, "sha256": brief.sha256} if brief else None,
        "dna": {"revision": dna.revision, "sha256": dna.sha256} if dna else None,
        "channel": {"brand_profile": project.channel.brand_profile,
                    "editorial_profile": project.channel.editorial_profile},
        "project": {"title": project.title, "topic": project.topic,
                    "content_type": project.content_type, "format": project.format,
                    "plan": project.plan, "script": project.script, "edl": project.edl,
                    "edl_revision_sha256": edl_revision.sha256 if edl_revision else None},
        "assets": assets,
        "claims": [
            {"id": claim.id, "revision": claim.revision,
             "status": claim.status, "text": claim.text,
             "source_url": claim.source_url, "source_title": claim.source_title,
             "support_excerpt": claim.support_excerpt,
             "published_at": claim.published_at.isoformat() if claim.published_at else None,
             "source_checked_at": (claim.source_checked_at.isoformat()
                                   if claim.source_checked_at else None)}
            for claim in claims
        ],
    }
    return content_sha256(snapshot), blockers


def review_read(db: Session, project: Project) -> dict:
    board = latest(db, CreativeStoryboardRevision, project.id)
    if board is None:
        raise HTTPException(404, "Creative storyboard not found")
    review = latest(db, CreativeReview, project.id)
    digest, blockers = review_snapshot(db, project, board)
    if not review:
        review_status = "REVIEW_REQUIRED"
    elif review.storyboard_revision != board.revision or review.snapshot_sha256 != digest:
        review_status = "STALE"
    elif blockers:
        review_status = "BLOCKED"
    elif review.decision == "APPROVE":
        review_status = "APPROVED_STORYBOARD"
    else:
        review_status = review.decision
    return {
        "status": review_status,
        "current_snapshot_sha256": digest,
        "blockers": blockers,
        "review": ({"id": review.id, "revision": review.revision,
                    "storyboard_revision": review.storyboard_revision,
                    "decision": review.decision, "actor": review.actor,
                    "notes": review.notes, "snapshot_sha256": review.snapshot_sha256,
                    "created_at": review.created_at.isoformat()} if review else None),
    }


def decide(db: Session, project_id: str, request: CreativeDecisionWrite) -> dict:
    project = project_for(db, project_id)
    board = latest(db, CreativeStoryboardRevision, project_id)
    if board is None:
        raise HTTPException(404, "Creative storyboard not found")
    require_revision(board, request.expected_storyboard_revision)
    current = latest(db, CreativeReview, project_id)
    require_revision(current, request.expected_revision)
    digest, blockers = review_snapshot(db, project, board)
    if request.expected_snapshot_sha256 != digest:
        raise HTTPException(409, "Creative inputs changed; reload review snapshot")
    if request.decision == "APPROVE":
        if blockers:
            raise HTTPException(409, {"code": "CREATIVE_REVIEW_BLOCKED", "reasons": blockers})
        if not (request.storyboard_reviewed and request.rights_checked
                and request.facts_checked):
            raise HTTPException(422, "Confirm storyboard, rights and factual checks")
    row = CreativeReview(
        project_id=project_id, revision=request.expected_revision + 1,
        storyboard_revision=board.revision, decision=request.decision,
        actor=request.actor, notes=request.notes, snapshot_sha256=digest,
    )
    db.add(row)
    try:
        db.flush()
        record_event(db, "CREATIVE_REVIEW_DECIDED", "project", project_id,
                     after={"decision": row.decision, "storyboard_revision": board.revision,
                            "snapshot_sha256": digest})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Creative review changed; reload before deciding") from exc
    db.expire_all()
    return review_read(db, project)
