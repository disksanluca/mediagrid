"""Vendor two pinned OFL fonts for offline compilation/render. Explicit authoring command."""

import base64
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps/renderer/src"
SOURCES = [
    (
        "Space Grotesk",
        "space-font",
        "spaceFontData",
        "floriankarsten/space-grotesk",
        "03507d024a01282884232081fc6011c09ff4e849",
        "fonts/ttf/static/SpaceGrotesk-Regular.ttf",
        "OFL.txt",
    ),
    (
        "IBM Plex Sans",
        "plex-font",
        "plexFontData",
        "IBM/plex",
        "71f558992315a12ca1f06a2215d57962a1992162",
        "packages/plex-sans/fonts/complete/ttf/IBMPlexSans-Regular.ttf",
        "LICENSE.txt",
    ),
]


def main():
    records = []
    for name, stem, symbol, repo, commit, file, license_file in SOURCES:
        base = f"https://raw.githubusercontent.com/{repo}/{commit}/"
        with urllib.request.urlopen(base + file, timeout=30) as response:
            data = response.read(2_000_000)
        if data[:4] != b"\0\1\0\0":
            raise ValueError("Expected TrueType")
        with urllib.request.urlopen(base + license_file, timeout=30) as response:
            license_text = response.read(100_000).decode()
        if "SIL OPEN FONT LICENSE" not in license_text.upper():
            raise ValueError("Expected OFL")
        digest = hashlib.sha256(data).hexdigest()
        (ROOT / f"{stem}.ts").write_text(
            f"// {name} Regular, unmodified; OFL-1.1. See {stem}-OFL.txt.\n"
            f"// Source: {base + file}\n// SHA256: {digest}\n"
            f'export const {symbol} = "data:font/ttf;base64,{base64.b64encode(data).decode()}";\n',
            encoding="utf-8",
            newline="\n",
        )
        (ROOT / f"{stem}-OFL.txt").write_text(license_text, encoding="utf-8", newline="\n")
        records.append(
            dict(
                family=name,
                style="Regular",
                weight=400,
                source=base + file,
                source_commit=commit,
                sha256=digest,
                bytes=len(data),
                license="OFL-1.1",
                license_source=base + license_file,
            )
        )
    (ROOT / "motion-font-provenance.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
