"""Bundle one pinned MIT model for offline Windows caption generation."""

import argparse
import hashlib
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO = "Systran/faster-whisper-base"
REVISION = "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"
MODEL_SHA256 = "d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9"
FILES = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt", "README.md")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    target = args.target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        try:
            cached = hf_hub_download(REPO, name, revision=REVISION, local_files_only=True)
        except FileNotFoundError:
            cached = hf_hub_download(REPO, name, revision=REVISION)
        shutil.copyfile(cached, target / name)
    if sha256(target / "model.bin") != MODEL_SHA256:
        raise RuntimeError("Pinned ASR model hash mismatch")
    print(f"Bundled {REPO}@{REVISION}: {target}")


if __name__ == "__main__":
    main()
