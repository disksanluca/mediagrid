import sys

from scripts import desktop_service
from workers.render import main as worker_module


def test_desktop_entry_does_not_pass_service_name_to_worker(monkeypatch) -> None:
    received = []
    monkeypatch.setattr(sys, "argv", ["mediagrid-service", "worker"])
    monkeypatch.setattr(worker_module, "main", lambda argv: received.append(argv))

    desktop_service.main()

    assert received == [[]]
