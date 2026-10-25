"""Canonical hashes for immutable creative content and approval dependencies."""

import hashlib
import json

from pydantic import BaseModel


def content_sha256(value: BaseModel | dict | list) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
