"""Lightweight in-process scheduler service.

Uses APScheduler (BackgroundScheduler) if available; degrades gracefully to a
no-op stub when APScheduler is not installed so that tests and dev starts still
work without the extra dependency.

Register APScheduler with:
    pip install apscheduler

Default jobs registered on startup:
  - okr_checkin_reminder  — daily, finds objectives with no check-in in 7 days,
                            creates notifications
  - weekly_digest         — Monday 8 AM, calls DigestService.generate_weekly()
  - proactive_scan        — daily, calls ProactiveScanner
"""
from __future__ import annotations

import logging
from typing import Any, Callable

_log = logging.getLogger(__name__)


class _NoOpScheduler:
    """Fallback when APScheduler is not installed."""

    def start(self) -> None:
        _log.info("SchedulerService: APScheduler not installed — running in no-op mode")

    def shutdown(self, wait: bool = False) -> None:
        pass

    def add_job(self, func: Callable, trigger: str, **kwargs: Any) -> str:
        _log.debug("SchedulerService (no-op): add_job %s trigger=%s", getattr(func, "__name__", func), trigger)
        return "noop"

    def remove_job(self, job_id: str) -> None:
        pass

    def list_jobs(self) -> list[dict[str, Any]]:
        return []

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return None

    @property
    def running(self) -> bool:
        return False


class SchedulerService:
    """Thin wrapper around APScheduler's BackgroundScheduler.

    All registered jobs are fire-and-forget; exceptions are logged but never
    propagate to the caller.
    """

    def __init__(self) -> None:
        self._scheduler = self._build_scheduler()
        self._jobs: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _build_scheduler() -> Any:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import]
            return BackgroundScheduler()
        except ImportError:
            return _NoOpScheduler()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    def shutdown(self, wait: bool = False) -> None:
        try:
            if self._scheduler.running:
                self._scheduler.shutdown(wait=wait)
        except Exception:
            pass

    # ── job management ────────────────────────────────────────────────────────

    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        *,
        hour: int = 0,
        minute: int = 0,
        day_of_week: str = "*",
        description: str = "",
    ) -> str:
        """Add or replace a cron-triggered job."""
        self._remove_if_exists(job_id)
        try:
            self._scheduler.add_job(
                self._wrap(func),
                "cron",
                id=job_id,
                hour=hour,
                minute=minute,
                day_of_week=day_of_week,
                replace_existing=True,
            )
        except Exception as exc:
            _log.warning("SchedulerService.add_cron_job(%s) failed: %s", job_id, exc)
        self._jobs[job_id] = {
            "job_id": job_id,
            "description": description,
            "trigger": f"cron hour={hour} minute={minute} day_of_week={day_of_week}",
            "func": getattr(func, "__name__", str(func)),
        }
        return job_id

    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        *,
        hours: int = 0,
        minutes: int = 0,
        description: str = "",
    ) -> str:
        """Add or replace an interval-triggered job."""
        self._remove_if_exists(job_id)
        try:
            self._scheduler.add_job(
                self._wrap(func),
                "interval",
                id=job_id,
                hours=hours,
                minutes=minutes,
                replace_existing=True,
            )
        except Exception as exc:
            _log.warning("SchedulerService.add_interval_job(%s) failed: %s", job_id, exc)
        self._jobs[job_id] = {
            "job_id": job_id,
            "description": description,
            "trigger": f"interval hours={hours} minutes={minutes}",
            "func": getattr(func, "__name__", str(func)),
        }
        return job_id

    def remove_job(self, job_id: str) -> None:
        self._remove_if_exists(job_id)
        self._jobs.pop(job_id, None)

    def list_jobs(self) -> list[dict[str, Any]]:
        return list(self._jobs.values())

    def trigger_now(self, job_id: str) -> dict[str, Any]:
        """Manually trigger a registered job immediately (best-effort)."""
        meta = self._jobs.get(job_id)
        if meta is None:
            raise KeyError(f"Job {job_id!r} not found")
        try:
            apjob = self._scheduler.get_job(job_id)
            if apjob is not None:
                apjob.modify(next_run_time=__import__("datetime").datetime.now())
                return {"status": "triggered", "job_id": job_id}
        except Exception:
            pass
        return {"status": "scheduled", "job_id": job_id, "note": "Job will run at next scheduled time"}

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _wrap(func: Callable) -> Callable:
        """Wrap a job function to swallow exceptions and log them."""
        def safe_wrapper(*args: Any, **kwargs: Any) -> None:
            try:
                func(*args, **kwargs)
            except Exception as exc:
                _log.exception("SchedulerService: job %s raised: %s", getattr(func, "__name__", "?"), exc)
        safe_wrapper.__name__ = getattr(func, "__name__", "wrapped")
        return safe_wrapper

    def _remove_if_exists(self, job_id: str) -> None:
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass


# ── Default job factories ─────────────────────────────────────────────────────

def register_default_jobs(scheduler: SchedulerService, service: Any) -> None:
    """Register the standard Friday background jobs onto the scheduler.

    Called once from apps/api/service.py after all services are wired.
    `service` is the FridayService instance.
    """

    # ── OKR check-in reminder (daily at 9am) ──────────────────────────────
    def okr_checkin_reminder() -> None:
        try:
            overdue = service.okrs.list_overdue_checkins(org_id="org-1", days=7)
            for obj in overdue:
                try:
                    service.notifications.create(
                        notification_id=f"reminder_{obj.obj_id}_{__import__('datetime').date.today()}",
                        recipient_id="user-1",
                        notification_type="okr_checkin_due",
                        title=f"Check-in due: {obj.title}",
                        body=f"No check-in recorded for '{obj.title}' in the last 7 days.",
                        entity_type="objective",
                        entity_id=obj.obj_id,
                    )
                except Exception:
                    pass
        except Exception as exc:
            _log.warning("okr_checkin_reminder: %s", exc)

    scheduler.add_cron_job(
        "okr_checkin_reminder",
        okr_checkin_reminder,
        hour=9,
        minute=0,
        description="Notify users of OKRs with no recent check-in",
    )

    # ── Weekly digest (Monday 8am) ─────────────────────────────────────────
    def weekly_digest() -> None:
        try:
            service.digest.generate_weekly(org_id="org-1")
        except Exception as exc:
            _log.warning("weekly_digest job: %s", exc)

    scheduler.add_cron_job(
        "weekly_digest",
        weekly_digest,
        hour=8,
        minute=0,
        day_of_week="mon",
        description="Generate and store the weekly digest",
    )

    # ── Proactive scan (daily at 7am) ─────────────────────────────────────
    def proactive_scan() -> None:
        try:
            service.proactive.scan_kpis()
        except Exception:
            pass
        try:
            service.proactive.scan_okrs()
        except Exception:
            pass

    scheduler.add_cron_job(
        "proactive_scan",
        proactive_scan,
        hour=7,
        minute=0,
        description="Daily proactive scan — KPI anomalies and OKR health alerts",
    )
