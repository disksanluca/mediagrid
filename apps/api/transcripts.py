"""Database helpers for versioned words and human-corrected captions."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .captions import Cue, Word
from .models import Transcript, TranscriptWord


def words_for(db: Session, transcript_id: str) -> list[Word]:
    stored = db.scalars(
        select(TranscriptWord).where(TranscriptWord.transcript_id == transcript_id)
        .order_by(TranscriptWord.position)
    )
    return [Word.model_validate({
        "start_ms": word.start_ms, "end_ms": word.end_ms,
        "text": word.text, "confidence": word.confidence,
        "speaker_id": word.speaker_id, "edited": word.edited,
    }) for word in stored]


def replace_words(db: Session, transcript: Transcript, words: list[Word]) -> None:
    db.execute(delete(TranscriptWord).where(TranscriptWord.transcript_id == transcript.id))
    db.add_all(TranscriptWord(
        transcript_id=transcript.id, position=index,
        **word.model_dump(),
    ) for index, word in enumerate(words))


def serialize(db: Session, transcript: Transcript) -> dict:
    return {
        "asset_id": transcript.asset_id, "source_sha256": transcript.source_sha256,
        "engine": transcript.engine, "model_id": transcript.model_id,
        "model_version": transcript.model_version, "language": transcript.language,
        "revision": transcript.revision, "status": transcript.status,
        "words": [word.model_dump() for word in words_for(db, transcript.id)],
        "cues": [cue.model_dump() for cue in map(Cue.model_validate, transcript.cues_json)],
    }
