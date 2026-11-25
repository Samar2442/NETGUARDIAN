import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("netguardian.migrations")

REMEDIATION_PHASE5A_COLUMNS = {
    "operation": "VARCHAR(64)",
    "parameters": "JSON DEFAULT '{}'",
    "execution_mode": "VARCHAR(20) DEFAULT 'SIMULATION'",
    "config_revision": "VARCHAR(64)",
    "approval_digest": "VARCHAR(64)",
    "executed_by": "VARCHAR(50)",
    "execution_started_at": "DATETIME",
    "execution_finished_at": "DATETIME",
}


def run_safe_migrations(engine: Engine) -> None:
    """
    Idempotent in-place schema upgrade for SQLite databases.
    Adds new Phase 5A columns to existing tables without destroying existing data.
    """
    if not str(engine.url).startswith("sqlite"):
        return

    with engine.connect() as conn:
        table_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='remediations'")
        ).fetchone()
        if not table_exists:
            return

        existing_cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(remediations)")).fetchall()
        }

        for col_name, col_def in REMEDIATION_PHASE5A_COLUMNS.items():
            if col_name not in existing_cols:
                logger.info(f"[*] Migrating remediations table: adding column '{col_name}'")
                conn.execute(text(f"ALTER TABLE remediations ADD COLUMN {col_name} {col_def}"))
        conn.commit()
