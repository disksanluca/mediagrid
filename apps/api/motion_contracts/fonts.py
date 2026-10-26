"""Measure the bundled OFL TrueType font; no OS fallback, network or recipe font paths."""

import base64
import hashlib
import re
import struct
from functools import lru_cache
from pathlib import Path


def font_source() -> Path:
    from apps.api.config import get_settings

    root = (
        get_settings().mediagrid_renderer_root
        or Path(__file__).resolve().parents[3] / "apps/renderer"
    )
    return root / "src/sports-font.ts"


@lru_cache(maxsize=2)
def metrics(source: str):
    match = re.search(r"data:font/ttf;base64,([A-Za-z0-9+/=]+)", source)
    if not match:
        raise ValueError("Bundled font unavailable")
    data = base64.b64decode(match[1], validate=True)

    def u16(p):
        return struct.unpack_from(">H", data, p)[0]

    def u32(p):
        return struct.unpack_from(">I", data, p)[0]

    tables = {}
    for i in range(u16(4)):
        p = 12 + i * 16
        tables[data[p : p + 4].decode("ascii")] = u32(p + 8)
    units = u16(tables["head"] + 18)
    count = u16(tables["hhea"] + 34)
    advances = [u16(tables["hmtx"] + i * 4) for i in range(count)]
    cmap = tables["cmap"]
    glyphs = {}
    # Unicode BMP format 4, adequate for the bundled Latin font. Reject missing glyphs.
    for i in range(u16(cmap + 2)):
        p = cmap + u32(cmap + 4 + i * 8 + 4)
        if u16(p) != 4:
            continue
        n = u16(p + 6) // 2
        end, start = p + 14, p + 16 + 2 * n
        delta, ranges = start + 2 * n, start + 4 * n
        for s in range(n):
            for cp in range(u16(start + 2 * s), min(65534, u16(end + 2 * s)) + 1):
                offset = u16(ranges + 2 * s)
                glyph = (
                    u16(ranges + 2 * s + offset + 2 * (cp - u16(start + 2 * s))) if offset else cp
                )
                if glyph:
                    glyph = (glyph + u16(delta + 2 * s)) & 65535
                if glyph:
                    glyphs[cp] = advances[min(glyph, count - 1)] / units
        break
    if not glyphs:
        raise ValueError("Bundled font has no supported Unicode cmap")
    return glyphs, hashlib.sha256(data).hexdigest()


def layout_text(text: str, size: float, width: float, max_lines: int) -> tuple[str, dict]:
    glyphs, digest = metrics(font_source().read_text(encoding="utf-8"))

    def measure(value):
        if any(ord(c) not in glyphs for c in value):
            raise ValueError("UNSUPPORTED_GLYPH: bundled font cannot display this text")
        return sum(glyphs[ord(c)] for c in value) * size

    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split(" "):
            if measure(word) > width:
                raise ValueError("TEXT_OVERFLOW: a word exceeds the approved text box")
            trial = (current + " " + word).lstrip()
            if measure(trial) > width:
                lines.append(current)
                current = word
            else:
                current = trial
        lines.append(current)
    if len(lines) > max_lines:
        raise ValueError("TEXT_OVERFLOW: too many lines; revise text or recipe parameters")
    return "\n".join(lines), {
        "font_sha256": digest,
        "widths": [round(measure(line), 6) for line in lines],
        "lines": len(lines),
    }
