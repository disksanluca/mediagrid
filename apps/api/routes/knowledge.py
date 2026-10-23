"""Per-claim source ledger for factual explainers, with human source review."""

import hashlib
import json
from datetime import UTC, date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import KnowledgeClaim, Project, ProjectStatus, now
from ..services import record_event

router = APIRouter(prefix="/projects", tags=["knowledge"])


class ClaimWrite(BaseModel):
    scene_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=5, max_length=300)
    source_url: HttpUrl
    source_title: str = Field(min_length=3, max_length=240)
    published_at: date | None = None
    support_excerpt: str = Field(min_length=10, max_length=500)

    @model_validator(mode="after")
    def readable(self) -> "ClaimWrite":
        if not all((self.text.strip(), self.source_title.strip(),
                    self.support_excerpt.strip())):
            raise ValueError("Claim, source title and evidence excerpt must be nonempty")
        if self.published_at and self.published_at > date.today():
            raise ValueError("Source publication date cannot be in the future")
        return self


class ClaimUpdate(ClaimWrite):
    expected_revision: int = Field(ge=1)


class ClaimApproval(BaseModel):
    expected_revision: int = Field(ge=1)
    source_opened: bool
    excerpt_matches: bool
    context_checked: bool


class ClaimRemove(BaseModel):
    expected_revision: int = Field(ge=1)


def current_claims(db: Session, project_id: str) -> list[KnowledgeClaim]:
    return list(db.scalars(select(KnowledgeClaim).where(
        KnowledgeClaim.project_id == project_id,
        KnowledgeClaim.status != "REMOVED",
    ).order_by(KnowledgeClaim.created_at, KnowledgeClaim.id)))


def serialize(claim: KnowledgeClaim) -> dict:
    checked_at = claim.source_checked_at
    if checked_at is not None and checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)
    return {
        "id": claim.id, "project_id": claim.project_id,
        "scene_id": claim.scene_id, "text": claim.text,
        "source_url": claim.source_url, "source_title": claim.source_title,
        "published_at": claim.published_at.isoformat() if claim.published_at else None,
        "source_checked_at": checked_at.isoformat() if checked_at else None,
        "support_excerpt": claim.support_excerpt,
        "revision": claim.revision, "status": claim.status,
        "reviewed_at": claim.reviewed_at.isoformat() if claim.reviewed_at else None,
    }


def claim_digest(claims: list[KnowledgeClaim]) -> str:
    canonical = json.dumps([serialize(claim) for claim in claims],
                           ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def project_for(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


def claim_for(db: Session, project_id: str, claim_id: str) -> KnowledgeClaim:
    claim = db.get(KnowledgeClaim, claim_id)
    if claim is None or claim.project_id != project_id or claim.status == "REMOVED":
        raise HTTPException(404, "Claim not found")
    return claim


def scene_check(project: Project, scene_id: str) -> None:
    if scene_id not in {str(scene.get("id")) for scene in
                        (project.plan or {}).get("scenes", [])}:
        raise HTTPException(422, "Select an existing project scene for the claim")


def invalidate_review(db: Session, project: Project) -> None:
    if project.status == ProjectStatus.APPROVED.value:
        project.plan = {key: value for key, value in (project.plan or {}).items()
                        if key != "review"}
        project.status = ProjectStatus.QC.value
        record_event(db, "PROJECT_APPROVAL_REVOKED", "project", project.id,
                     after={"reason": "knowledge_claim_changed"})


def invalidate_claim_approvals(db: Session, project: Project) -> None:
    """A changed script requires fresh human review of its factual claims."""
    if project.content_type not in {"knowledge", "motion_ad"}:
        return
    for claim in current_claims(db, project.id):
        if claim.status == "APPROVED":
            claim.status = "REVIEW_REQUIRED"
            claim.reviewed_at = None
            claim.revision += 1
            record_event(db, "KNOWLEDGE_CLAIM_REVIEW_REVOKED", "knowledge_claim",
                         claim.id, after={"reason": "project_script_changed",
                                          "revision": claim.revision})


@router.get("/{project_id}/claims")
def list_claims(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    project_for(db, project_id)
    return [serialize(item) for item in current_claims(db, project_id)]


@router.post("/{project_id}/claims", status_code=status.HTTP_201_CREATED)
def add_claim(project_id: str, payload: ClaimWrite,
              db: Session = Depends(get_db)) -> dict:
    project = project_for(db, project_id)
    scene_check(project, payload.scene_id)
    invalidate_review(db, project)
    if project.content_type != "motion_ad":
        project.content_type = "knowledge"
    claim = KnowledgeClaim(
        project_id=project_id, scene_id=payload.scene_id,
        text=payload.text.strip(), source_url=str(payload.source_url),
        source_title=payload.source_title.strip(), published_at=payload.published_at,
        support_excerpt=payload.support_excerpt.strip(),
    )
    db.add(claim)
    db.flush()
    record_event(db, "KNOWLEDGE_CLAIM_ADDED", "knowledge_claim", claim.id,
                 after={"project_id": project_id, "revision": 1})
    db.commit()
    return serialize(claim)


@router.put("/{project_id}/claims/{claim_id}")
def edit_claim(project_id: str, claim_id: str, payload: ClaimUpdate,
               db: Session = Depends(get_db)) -> dict:
    project = project_for(db, project_id)
    claim = claim_for(db, project_id, claim_id)
    if claim.revision != payload.expected_revision:
        raise HTTPException(409, "Claim changed; reload before saving")
    scene_check(project, payload.scene_id)
    invalidate_review(db, project)
    if (claim.source_url != str(payload.source_url)
            or claim.support_excerpt != payload.support_excerpt.strip()):
        claim.source_checked_at = None
    claim.scene_id = payload.scene_id
    claim.text = payload.text.strip()
    claim.source_url = str(payload.source_url)
    claim.source_title = payload.source_title.strip()
    claim.published_at = payload.published_at
    claim.support_excerpt = payload.support_excerpt.strip()
    claim.revision += 1
    claim.status = "REVIEW_REQUIRED"
    claim.reviewed_at = None
    record_event(db, "KNOWLEDGE_CLAIM_EDITED", "knowledge_claim", claim.id,
                 after={"revision": claim.revision})
    db.commit()
    return serialize(claim)


@router.post("/{project_id}/claims/{claim_id}/approve")
def approve_claim(project_id: str, claim_id: str, payload: ClaimApproval,
                  db: Session = Depends(get_db)) -> dict:
    project = project_for(db, project_id)
    claim = claim_for(db, project_id, claim_id)
    if claim.revision != payload.expected_revision:
        raise HTTPException(409, "Claim changed; reload before approving")
    if claim.status == "APPROVED":
        raise HTTPException(409, "Claim is already approved")
    scene_check(project, claim.scene_id)
    if not all((payload.source_opened, payload.excerpt_matches,
                payload.context_checked)):
        raise HTTPException(422, "Open the source and confirm excerpt and context")
    claim.status = "APPROVED"
    claim.reviewed_at = now()
    record_event(db, "KNOWLEDGE_CLAIM_APPROVED", "knowledge_claim", claim.id,
                 after={"revision": claim.revision, "source_url": claim.source_url})
    db.commit()
    return serialize(claim)


@router.post("/{project_id}/claims/{claim_id}/remove")
def remove_claim(project_id: str, claim_id: str, payload: ClaimRemove,
                 db: Session = Depends(get_db)) -> dict:
    project = project_for(db, project_id)
    claim = claim_for(db, project_id, claim_id)
    if claim.revision != payload.expected_revision:
        raise HTTPException(409, "Claim changed; reload before removing")
    invalidate_review(db, project)
    claim.revision += 1
    claim.status = "REMOVED"
    claim.reviewed_at = None
    record_event(db, "KNOWLEDGE_CLAIM_REMOVED", "knowledge_claim", claim.id,
                 after={"revision": claim.revision})
    db.commit()
    return serialize(claim)
