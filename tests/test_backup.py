import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path

import pytest

from apps.api.backup import create_backup, restore_backup


def _sample_data(root: Path) -> None:
    (root / "Database").mkdir(parents=True)
    with closing(sqlite3.connect(root / "Database" / "mediagrid.db")) as db:
        db.execute("CREATE TABLE note (value TEXT)")
        db.execute("INSERT INTO note VALUES ('original')")
        db.commit()
    (root / "assets").mkdir()
    (root / "assets" / "sample.txt").write_text("original", encoding="utf-8")
    (root / "settings.json").write_text('{"setup_complete": true}', encoding="utf-8")


def test_backup_roundtrip_keeps_previous_data(tmp_path: Path) -> None:
    data = tmp_path / "Data"
    _sample_data(data)
    archive = tmp_path / "portable.mgrid"
    manifest = create_backup(data, archive)
    assert manifest["version"] == 1
    (data / "assets" / "sample.txt").write_text("changed", encoding="utf-8")
    previous = restore_backup(data, archive)
    assert previous is not None
    assert (previous / "assets" / "sample.txt").read_text() == "changed"
    assert (data / "assets" / "sample.txt").read_text() == "original"
    assert json.loads((data / "settings.json").read_text())["setup_complete"] is True
    with closing(sqlite3.connect(data / "Database" / "mediagrid.db")) as db:
        assert db.execute("SELECT value FROM note").fetchone()[0] == "original"


def test_restore_rejects_modified_archive_without_touching_data(tmp_path: Path) -> None:
    data = tmp_path / "Data"
    _sample_data(data)
    archive = tmp_path / "portable.mgrid"
    create_backup(data, archive)
    damaged = tmp_path / "damaged.mgrid"
    with zipfile.ZipFile(archive) as original, zipfile.ZipFile(damaged, "w") as target:
        for name in original.namelist():
            content = original.read(name)
            target.writestr(name, b"modified" if name == "data/assets/sample.txt" else content)
    with pytest.raises(ValueError, match="integridade"):
        restore_backup(data, damaged)
    assert (data / "assets" / "sample.txt").read_text() == "original"


def test_restore_rejects_path_traversal(tmp_path: Path) -> None:
    data = tmp_path / "Data"
    _sample_data(data)
    archive = tmp_path / "evil.mgrid"
    manifest = {
        "format": "MediaGrid Backup",
        "version": 1,
        "files": [{"path": "data/../escape.txt", "size": 0, "sha256": "0" * 64}],
    }
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("data/../escape.txt", b"")
        target.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(ValueError, match="Caminho inválido"):
        restore_backup(data, archive)
    assert not (tmp_path / "escape.txt").exists()


def test_restore_archive_stored_inside_data_directory(tmp_path: Path) -> None:
    data = tmp_path / "Data"
    _sample_data(data)
    archive = data / "backups" / "portable.mgrid"
    create_backup(data, archive)
    (data / "assets" / "sample.txt").write_text("changed", encoding="utf-8")
    previous = restore_backup(data, archive)
    assert previous is not None
    assert (data / "assets" / "sample.txt").read_text() == "original"
    assert (previous / "backups" / "portable.mgrid").is_file()
