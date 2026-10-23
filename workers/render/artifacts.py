"""Promote a render artifact only while its worker still owns the job lease."""

from pathlib import Path

from sqlalchemy.orm import Session

from apps.api.models import Job, JobStatus, Project, ProjectStatus, now
from apps.api.services import fence_job_completion, record_event


def finish_render_attempt(
    db: Session, job: Job, project: Project, lease_owner: str,
    staged: Path, final: Path,
) -> bool:
    """Commit a terminal job and atomically replace its MP4 after a valid fence.

    A stale worker can leave only its unique staged file, never overwrite the
    project-named output. Filesystem and database commits are not one atomic
    operation; the project stays hidden from downloads until the DB commit.
    """
    try:
        if not fence_job_completion(db, job.id, lease_owner):
            db.rollback()
            return False
        if job.status == JobStatus.SUCCEEDED.value:
            try:
                staged.replace(final)
            except OSError as exc:
                job.status = JobStatus.FAILED.value
                job.error = f"Render artifact could not be promoted: {exc}"
                job.result = None
                job.finished_at = now()
                project.status = ProjectStatus.FAILED.value
                project.error = job.error
                record_event(
                    db, "RENDER_FAILED", "project", project.id,
                    after={"error": job.error},
                )
            else:
                record_event(db, "RENDER_FINISHED", "project", project.id,
                             after=job.result)
        db.commit()
        return True
    finally:
        staged.unlink(missing_ok=True)
