"""Read-only IBGE research and local Geo project creation."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Channel
from ..official_geo import fetch_municipality, import_municipality, search_municipalities
from ..schemas import ProjectRead

router = APIRouter(prefix="/geo", tags=["geo"])


class ImportMunicipality(BaseModel):
    channel_id: str
    municipality_id: int


@router.get("/municipalities")
def list_municipalities(
    query: str = Query(min_length=3, max_length=80),
) -> list[dict[str, str | int]]:
    if len(query.strip()) < 3:
        raise HTTPException(422, "Use pelo menos três caracteres na busca")
    try:
        return search_municipalities(query)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Não foi possível consultar os municípios no IBGE agora") from exc


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_from_ibge(payload: ImportMunicipality, db: Session = Depends(get_db)):
    channel = db.get(Channel, payload.channel_id)
    if channel is None:
        raise HTTPException(404, "Canal não encontrado")
    if channel.default_engine != "geo":
        raise HTTPException(422, "Escolha um canal com motor Geo")
    if payload.municipality_id <= 0:
        raise HTTPException(422, "Identificador de município inválido")
    try:
        municipality = fetch_municipality(payload.municipality_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(404, "Município não encontrado no IBGE") from exc
        raise HTTPException(503, "Não foi possível consultar o IBGE agora") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Não foi possível consultar o IBGE agora") from exc
    project = import_municipality(db, channel, municipality)
    db.commit()
    db.refresh(project)
    return project
