import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.database.session import engine, SessionLocal, Base
from app.database.migrations import run_safe_migrations
from app.database.seed import seed_database
from app.websocket.manager import ws_manager
from app.engines.monitoring.monitoring_engine import MonitoringEngine
from app.engines.scoring.health_engine import HealthScoringEngine

# Import API Routers
from app.api.v1.auth import router as auth_router
from app.api.v1.devices import router as devices_router
from app.api.v1.interfaces import router as interfaces_router
from app.api.v1.vlans import router as vlans_router
from app.api.v1.routes import router as routes_router
from app.api.v1.topology import router as topology_router
from app.api.v1.monitoring import router as monitoring_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.diagnostics import router as diagnostics_router
from app.api.v1.simulator import router as simulator_router
from app.api.v1.remediation import router as remediation_router
from app.api.v1.training import router as training_router
from app.api.v1.drift import router as drift_router
from app.api.v1.audit import router as audit_router
from app.api.v1.campus_inventory import router as campus_inventory_router
from app.api.v1.telemetry import router as telemetry_router
from app.api.v1.events import router as events_router
from app.api.v1.simulation import router as simulation_router
from app.services.telemetry_scheduler import telemetry_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("netguardian")

async def background_monitoring_worker():
    """Background task polling devices and broadcasting telemetry via WebSocket."""
    while True:
        try:
            await asyncio.sleep(settings.MONITORING_INTERVAL_SECONDS)
            db = SessionLocal()
            try:
                # Run polling
                MonitoringEngine.run_polling_cycle(db)
                health = HealthScoringEngine.calculate_health(db)
                # Broadcast live health update
                await ws_manager.broadcast({
                    "type": "TELEMETRY_UPDATE",
                    "data": health
                })
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Background monitoring worker error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[*] Starting NetGuardian Backend...")
    # Initialize DB & Seed data if needed
    import os
    if not os.getenv("TESTING"):
        Base.metadata.create_all(bind=engine)
        run_safe_migrations(engine)
        try:
            seed_database()
        except Exception as e:
            logger.warning(f"Seed note: {e}")
    
    worker_task = None
    import os
    if not os.getenv("TESTING"):
        telemetry_scheduler.start()
    
    yield
    
    await telemetry_scheduler.stop()
    if worker_task:
        worker_task.cancel()
    logger.info("[*] NetGuardian Backend stopped.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Intelligent Network Fault Detection, Root-Cause Analysis, Digital Twin & Explainable Self-Healing Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(devices_router, prefix=settings.API_V1_STR)
app.include_router(interfaces_router, prefix=settings.API_V1_STR)
app.include_router(vlans_router, prefix=settings.API_V1_STR)
app.include_router(routes_router, prefix=settings.API_V1_STR)
app.include_router(topology_router, prefix=settings.API_V1_STR)
app.include_router(monitoring_router, prefix=settings.API_V1_STR)
app.include_router(incidents_router, prefix=settings.API_V1_STR)
app.include_router(diagnostics_router, prefix=settings.API_V1_STR)
app.include_router(simulator_router, prefix=settings.API_V1_STR)
app.include_router(remediation_router, prefix=settings.API_V1_STR)
app.include_router(training_router, prefix=settings.API_V1_STR)
app.include_router(drift_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(campus_inventory_router, prefix=settings.API_V1_STR)
app.include_router(telemetry_router, prefix=settings.API_V1_STR)
app.include_router(events_router, prefix=settings.API_V1_STR)
app.include_router(simulation_router, prefix=settings.API_V1_STR)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection open & receive any client pings
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

@app.get("/")
def root():
    return {
        "platform": settings.PROJECT_NAME,
        "tagline": settings.TAGLINE,
        "status": "OPERATIONAL",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "netguardian-api"}
