from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Channel
from ..official_politics import fetch_proposal, import_proposal, search_proposals
from ..schemas import ProjectRead

router = APIRouter(prefix="/politics", tags=["politics"])


class ImportProposal(BaseModel):
    channel_id: str
    proposal_id: int


@router.get("/proposals")
def list_official_proposals(
    query: str = Query(default="", max_length=80),
    year: int = Query(default_factory=lambda: datetime.now(UTC).year, ge=1990, le=2100),
) -> list[dict[str, str | int]]:
    if query and len(query.strip()) < 3:
        raise HTTPException(422, "Use pelo menos três caracteres na busca")
    try:
        return search_proposals(query.strip(), year)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Não foi possível consultar a Câmara agora") from exc


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_from_official_proposal(
    payload: ImportProposal, db: Session = Depends(get_db)
):
    channel = db.get(Channel, payload.channel_id)
    if channel is None:
        raise HTTPException(404, "Canal não encontrado")
    if channel.default_engine != "politics":
        raise HTTPException(422, "Escolha um canal com motor Política")
    if payload.proposal_id <= 0:
        raise HTTPException(422, "Identificador inválido")
    try:
        proposal, current_status = fetch_proposal(payload.proposal_id)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Não foi possível abrir a proposição na Câmara") from exc
    if len(str(proposal["summary"])) > 1200:
        raise HTTPException(422, "Ementa extensa demais para um roteiro curto; escolha outra pauta")
    try:
        project = import_proposal(db, channel, proposal, current_status)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(503, "Registro oficial incompleto para gerar evidências") from exc
    db.refresh(project)
    return project
