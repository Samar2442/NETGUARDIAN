import asyncio
import logging
import threading
from typing import Optional
from app.core.config import settings
from app.database.session import SessionLocal
from app.services.telemetry_engine import TelemetryEngine
from app.websocket.manager import ws_manager

logger = logging.getLogger("netguardian.scheduler")


class TelemetryScheduler:
    """
    Controlled single-instance background telemetry collection scheduler.
    NOTE: In multi-worker ASGI deployments, an external distributed scheduler
    should coordinate collection to avoid duplicate per-worker runs.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._cycles_completed = 0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def cycles_completed(self) -> int:
        return self._cycles_completed

    async def _loop(self) -> None:
        prune_counter = 0
        while self._running:
            try:
                if settings.TELEMETRY_ENABLED:
                    def _run_sync():
                        db = SessionLocal()
                        try:
                            from app.services.incident_lifecycle import IncidentLifecycleService
                            res = TelemetryEngine.collect_once(db)
                            IncidentLifecycleService.evaluate_escalations(db)
                            return res
                        finally:
                            db.close()

                    summary = await asyncio.to_thread(_run_sync)
                    self._cycles_completed += 1
                    prune_counter += 1
                    if prune_counter >= 60:
                        prune_counter = 0
                        def _prune_sync():
                            db = SessionLocal()
                            try:
                                TelemetryEngine.prune_old_telemetry(db)
                            finally:
                                db.close()
                        await asyncio.to_thread(_prune_sync)

                    if summary.get("status") == "COLLECTED":
                        await ws_manager.broadcast({
                            "type": "TELEMETRY_UPDATE",
                            "source": "SIMULATION",
                            "data": summary,
                        })
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"[TelemetryScheduler] Cycle isolated error: {exc}")

            await asyncio.sleep(settings.TELEMETRY_POLLING_INTERVAL_SECONDS)

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return False  # Prevent duplicate scheduler instances
            self._running = True
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._loop())
            logger.info("[TelemetryScheduler] Started background simulation scheduler.")
            return True

    async def stop(self) -> None:
        with self._lock:
            self._running = False
            task = self._task
            self._task = None
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("[TelemetryScheduler] Stopped.")


telemetry_scheduler = TelemetryScheduler()
