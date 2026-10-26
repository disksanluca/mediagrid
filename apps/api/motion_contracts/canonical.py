"""mg-canonical-json-v1: finite six-decimal JSON, UTF-8, sorted keys, no whitespace."""

import hashlib
import json
import math
from decimal import Decimal

from pydantic import BaseModel

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_JSON_DEPTH = 24


def canonical_bytes(value: BaseModel | dict | list) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")

    def encode(item, depth=0):
        if depth > MAX_JSON_DEPTH:
            raise ValueError("JSON depth limit exceeded")
        if item is None:
            return "null"
        if type(item) is bool:
            return "true" if item else "false"
        if type(item) in (int, float):
            if abs(item) > 2**53 - 1 or not math.isfinite(item):
                raise ValueError("Number must be finite and JSON-safe")
            number = Decimal(str(item))
            if number != number.quantize(Decimal("0.000001")):
                raise ValueError("Numbers allow at most six decimal places")
            if number == 0:
                return "0"
            return format(number, "f").rstrip("0").rstrip(".") if "." in format(
                number, "f"
            ) else format(number, "f")
        if type(item) is str:
            return json.dumps(item, ensure_ascii=False, allow_nan=False)
        if type(item) is list:
            return "[" + ",".join(encode(v, depth+1) for v in item) + "]"
        if type(item) is dict and all(type(k) is str for k in item):
            return "{" + ",".join(
                encode(k, depth+1) + ":" + encode(item[k], depth+1) for k in sorted(item)
            ) + "}"
        raise ValueError("Only JSON data is supported")

    try:
        encoded = encode(value).encode("utf-8")
    except (RecursionError, UnicodeError) as exc:
        raise ValueError("Invalid JSON nesting or Unicode") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise ValueError("JSON exceeds 2 MiB")
    return encoded


def contract_sha256(value: BaseModel | dict | list) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_json(data: bytes) -> dict:
    """Size/depth/duplicate-key gate before Pydantic; no paths or URLs are accepted."""
    if not isinstance(data, bytes) or len(data) > MAX_JSON_BYTES:
        raise ValueError("JSON must be bytes of at most 2 MiB")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                            parse_constant=invalid_constant)
        canonical_bytes(result)
    except (RecursionError, UnicodeError) as exc:
        raise ValueError("Invalid JSON nesting or Unicode") from exc
    if not isinstance(result, dict):
        raise ValueError("Contract must be a JSON object")
    return result
