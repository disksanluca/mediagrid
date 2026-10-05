"""Portable local backups for the Windows desktop application."""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

BACKUP_VERSION = 1
DATA_FOLDERS = ("assets", "exports", "renders", "voice", "transcripts", "models")


def _copy_into_archive(archive: zipfile.ZipFile, source: Path, name: str) -> dict[str, object]:
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as input_file, archive.open(name, "w", force_zip64=True) as output:
        while chunk := input_file.read(1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    return {"path": name, "size": size, "sha256": digest.hexdigest()}


def create_backup(
    data_dir: Path,
    destination: Path,
    *,
    include_assets: bool = True,
    include_renders: bool = True,
    include_models: bool = False,
) -> dict[str, object]:
    """Write a versioned .mgrid archive, including a consistent SQLite snapshot."""
    data_dir = data_dir.resolve()
    database = data_dir / "Database" / "mediagrid.db"
    if not database.is_file():
        raise ValueError("Banco local não encontrado para o backup.")
    destination = destination.resolve()
    if destination.is_relative_to(data_dir) and not destination.is_relative_to(data_dir / "backups"):
        raise ValueError("Salve o backup fora da pasta de dados ou dentro de Backups.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
    included = {
        "assets": include_assets,
        "exports": include_renders,
        "renders": include_renders,
        "voice": True,
        "transcripts": True,
        "models": include_models,
    }
    try:
        with tempfile.TemporaryDirectory(prefix="mediagrid-backup-") as staging:
            snapshot = Path(staging) / "mediagrid.db"
            with sqlite3.connect(database) as source, sqlite3.connect(snapshot) as target:
                source.backup(target)
            sources = [(snapshot, "data/Database/mediagrid.db")]
            settings = data_dir / "settings.json"
            if settings.is_file():
                sources.append((settings, "data/settings.json"))
            for folder in DATA_FOLDERS:
                if not included[folder]:
                    continue
                root = data_dir / folder
                if not root.is_dir():
                    continue
                for path in sorted(root.rglob("*")):
                    if path.is_file() and not path.is_symlink():
                        sources.append((path, f"data/{path.relative_to(data_dir).as_posix()}"))
            manifest: dict[str, object] = {
                "format": "MediaGrid Backup",
                "version": BACKUP_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "includes": included,
                "files": [],
            }
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                files = manifest["files"]
                assert isinstance(files, list)
                for source, name in sources:
                    files.append(_copy_into_archive(archive, source, name))
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        os.replace(temporary, destination)
        return manifest
    finally:
        temporary.unlink(missing_ok=True)


def _valid_entry(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or "\\" in name or ".." in path.parts or path.as_posix() != name:
        return False
    if name == "data/settings.json":
        return True
    if len(path.parts) < 3 or path.parts[0] != "data":
        return False
    return path.parts[1] in (*DATA_FOLDERS, "Database")


def restore_backup(data_dir: Path, archive_path: Path) -> Path | None:
    """Validate first, then replace data atomically and keep the previous folder."""
    data_dir = data_dir.resolve()
    archive_path = archive_path.resolve()
    if not archive_path.is_file():
        raise ValueError("Arquivo de backup não encontrado.")
    if archive_path.is_relative_to(data_dir):
        with tempfile.NamedTemporaryFile(
            prefix="mediagrid-restore-", suffix=".mgrid", dir=data_dir.parent, delete=False
        ) as temporary:
            copy_path = Path(temporary.name)
        try:
            shutil.copyfile(archive_path, copy_path)
            return restore_backup(data_dir, copy_path)
        finally:
            copy_path.unlink(missing_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if names.count("manifest.json") != 1 or len(names) != len(set(names)):
            raise ValueError("Backup com entradas duplicadas ou sem manifesto.")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != "MediaGrid Backup" or manifest.get("version") != BACKUP_VERSION:
            raise ValueError("Versão de backup incompatível.")
        listed = manifest.get("files")
        if not isinstance(listed, list) or not listed:
            raise ValueError("Manifesto de backup inválido.")
        expected = {}
        for item in listed:
            if not isinstance(item, dict):
                raise ValueError("Manifesto de backup inválido.")
            name, size, digest = item.get("path"), item.get("size"), item.get("sha256")
            if not isinstance(name, str) or not _valid_entry(name) or name in expected:
                raise ValueError("Caminho inválido no backup.")
            if not isinstance(size, int) or size < 0 or not isinstance(digest, str) or len(digest) != 64:
                raise ValueError("Tamanho ou checksum inválido no backup.")
            try:
                info = archive.getinfo(name)
            except KeyError as error:
                raise ValueError("Arquivo declarado ausente no backup.") from error
            if info.is_dir() or info.file_size != size or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError("Entrada inválida no backup.")
            expected[name] = (size, digest)
        if set(names) != {"manifest.json", *expected} or "data/Database/mediagrid.db" not in expected:
            raise ValueError("O backup contém arquivos não declarados ou está sem o banco.")
        needed = sum(size for size, _ in expected.values())
        data_dir.parent.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(data_dir.parent).free < needed:
            raise ValueError("Espaço livre insuficiente para restaurar o backup.")
        staging = data_dir.with_name(f".{data_dir.name}.restore-{uuid.uuid4().hex}")
        staging.mkdir()
        try:
            for name, (size, digest) in expected.items():
                target = staging.joinpath(*PurePosixPath(name).parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                actual = hashlib.sha256()
                written = 0
                with archive.open(name) as source, target.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        written += len(chunk)
                        if written > size:
                            raise ValueError("Tamanho de arquivo inválido no backup.")
                        output.write(chunk)
                        actual.update(chunk)
                if written != size or actual.hexdigest() != digest:
                    raise ValueError("Verificação de integridade do backup falhou.")
            database = staging / "Database" / "mediagrid.db"
            with sqlite3.connect(database) as connection:
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Banco do backup está corrompido.")
            previous = None
            if data_dir.exists():
                previous = data_dir.with_name(
                    f"{data_dir.name}.before-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
                )
                os.replace(data_dir, previous)
            try:
                os.replace(staging, data_dir)
            except OSError:
                if previous is not None:
                    os.replace(previous, data_dir)
                raise
            return previous
        finally:
            if staging.exists():
                shutil.rmtree(staging)
