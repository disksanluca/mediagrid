"""Promote a render artifact only while its worker still owns the job lease."""

from pathlib import Path

from sqlalchemy.orm import Session

from apps.api.ingestion import sha256_file
from apps.api.models import Asset, Job, JobStatus, Project, ProjectStatus, now
from apps.api.services import fence_job_completion, record_event
from workers.render.proxy import ProxyBuild


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
                job.progress = 0
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


def finish_media_render_attempt(
    db: Session, job: Job, lease_owner: str, staged: Path, final: Path,
) -> bool:
    """Promote a clip/caption/football/3D MP4 under its current job lease."""
    try:
        if not fence_job_completion(db, job.id, lease_owner):
            db.rollback()
            return False
        if job.status == JobStatus.SUCCEEDED.value:
            try:
                staged.replace(final)
            except OSError as exc:
                job.status = JobStatus.FAILED.value
                job.error = f"Media artifact could not be promoted: {exc}"
                job.result = None
                job.progress = 0
                record_event(db, f"{job.job_type}_FAILED", "job", job.id,
                             after={"error": job.error})
            else:
                record_event(db, f"{job.job_type}_FINISHED", "job", job.id,
                             after=job.result)
        db.commit()
        return True
    finally:
        staged.unlink(missing_ok=True)


def finish_voice_attempt(
    db: Session, job: Job, lease_owner: str,
    staged_audio: Path, final_audio: Path,
    staged_manifest: Path, final_manifest: Path,
) -> bool:
    """Only the current lease may promote the WAV and its script digest."""
    try:
        if not fence_job_completion(db, job.id, lease_owner):
            db.rollback()
            return False
        if job.status == JobStatus.SUCCEEDED.value:
            try:
                if not staged_audio.is_file() or not staged_manifest.is_file():
                    raise FileNotFoundError("Voice WAV or script digest is missing")
                staged_audio.replace(final_audio)
                staged_manifest.replace(final_manifest)
            except OSError as exc:
                job.status = JobStatus.FAILED.value
                job.error = f"Voice artifact could not be promoted: {exc}"
                job.result = None
                job.progress = 0
                record_event(db, "VOICE_FAILED", "job", job.id,
                             after={"error": job.error})
            else:
                record_event(db, "VOICE_FINISHED", "job", job.id,
                             after=job.result)
        db.commit()
        return True
    finally:
        staged_audio.unlink(missing_ok=True)
        staged_manifest.unlink(missing_ok=True)


def finish_proxy_attempt(
    db: Session, job: Job, asset: Asset, lease_owner: str, build: ProxyBuild,
) -> bool:
    """Publish verified proxy files and ingest metadata under the active lease."""
    try:
        if not fence_job_completion(db, job.id, lease_owner):
            db.rollback()
            return False
        if job.status == JobStatus.SUCCEEDED.value:
            try:
                if (not build.staged_proxy.is_file()
                        or sha256_file(build.staged_proxy) != build.result["proxy_sha256"]):
                    raise ValueError("Staged proxy is missing or changed")
                if build.staged_waveform is not None and (
                    not build.staged_waveform.is_file()
                    or sha256_file(build.staged_waveform) != build.result["waveform_sha256"]
                ):
                    raise ValueError("Staged waveform is missing or changed")
                build.staged_proxy.replace(build.final_proxy)
                if build.staged_waveform is not None:
                    build.staged_waveform.replace(build.final_waveform)
            except (OSError, ValueError) as exc:
                job.status = JobStatus.FAILED.value
                job.error = f"Proxy artifact could not be promoted: {exc}"
                job.result = None
                job.progress = 0
                asset.metadata_json = {
                    **(asset.metadata_json or {}), "ingest_status": "FAILED",
                }
                record_event(db, "PROXY_FAILED", "job", job.id,
                             after={"error": job.error})
            else:
                asset.metadata_json = build.metadata
                record_event(db, "PROXY_FINISHED", "job", job.id,
                             after=job.result)
        db.commit()
        return True
    finally:
        build.staged_proxy.unlink(missing_ok=True)
        if build.staged_waveform is not None:
            build.staged_waveform.unlink(missing_ok=True)
