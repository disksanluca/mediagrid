"""Keep a claimed local job alive while a blocking encoder or Blender process runs."""

import logging
from collections.abc import Callable
from threading import Event, Thread

from sqlalchemy.exc import SQLAlchemyError

from apps.api.database import SessionLocal
from apps.api.services import renew_job_lease

logger = logging.getLogger(__name__)


def start_lease_heartbeat(job_id: str, worker_id: str | None,
                          *, interval_seconds: float = 30) -> Callable[[], None]:
    if not worker_id:
        return lambda: None
    stopped = Event()

    def beat() -> None:
        while not stopped.wait(interval_seconds):
            try:
                with SessionLocal() as db:
                    if not renew_job_lease(db, job_id, worker_id):
                        return
                    db.commit()
            except SQLAlchemyError:
                logger.warning("Could not renew job lease %s; will retry", job_id,
                               exc_info=True)

    thread = Thread(target=beat, name=f"mediagrid-lease-{job_id[:8]}", daemon=True)
    thread.start()

    def stop() -> None:
        stopped.set()
        thread.join(timeout=1)

    return stop
