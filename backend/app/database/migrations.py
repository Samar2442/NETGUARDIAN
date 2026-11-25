import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("netguardian.migrations")

TABLE_MIGRATIONS = {
    "remediations": {
        "operation": "VARCHAR(64)",
        "parameters": "JSON DEFAULT '{}'",
        "execution_mode": "VARCHAR(20) DEFAULT 'SIMULATION'",
        "config_revision": "VARCHAR(64)",
        "approval_digest": "VARCHAR(64)",
        "executed_by": "VARCHAR(50)",
        "execution_started_at": "DATETIME",
        "execution_finished_at": "DATETIME",
    },
    "devices": {
        "department": "VARCHAR(100)",
        "vlan_id": "INTEGER",
        "mac_address": "VARCHAR(20)",
        "connected_switch_id": "VARCHAR(36)",
        "connected_interface": "VARCHAR(50)",
        "asset_category": "VARCHAR(40) DEFAULT 'infrastructure'",
        "layer": "VARCHAR(30)",
    },
    "vlans": {
        "department": "VARCHAR(100)",
    },
    "network_links": {
        "admin_status": "VARCHAR(10) DEFAULT 'up'",
        "duplex": "VARCHAR(10) DEFAULT 'full'",
        "allowed_vlans": "VARCHAR(255)",
        "utilization_pct": "FLOAT DEFAULT 12.0",
        "last_state_change": "DATETIME",
    },
    "events": {
        "event_code": "VARCHAR(60)",
        "device_id": "VARCHAR(36)",
        "interface_id": "VARCHAR(36)",
        "vlan_id": "INTEGER",
        "correlation_id": "VARCHAR(64)",
        "acknowledged": "BOOLEAN DEFAULT 0",
        "resolved": "BOOLEAN DEFAULT 0",
    },
    "incidents": {
        "priority": "VARCHAR(10) DEFAULT 'P2'",
        "lifecycle_state": "VARCHAR(30) DEFAULT 'NEW'",
        "affected_interface_ids": "JSON DEFAULT '[]'",
        "root_event_id": "VARCHAR(36)",
        "correlation_id": "VARCHAR(64)",
        "assigned_to": "VARCHAR(50)",
        "assigned_at": "DATETIME",
        "escalation_level": "INTEGER DEFAULT 0",
        "escalated_at": "DATETIME",
        "acknowledged_at": "DATETIME",
        "acknowledged_by": "VARCHAR(50)",
        "closed_at": "DATETIME",
        "source": "VARCHAR(30) DEFAULT 'SIMULATION'",
    },
}


def run_safe_migrations(engine: Engine) -> None:
    """
    Idempotent in-place schema upgrade for SQLite databases.
    Adds new columns to existing tables without destroying existing data.
    """
    if not str(engine.url).startswith("sqlite"):
        return

    with engine.connect() as conn:
        for table_name, columns in TABLE_MIGRATIONS.items():
            table_exists = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:tname"),
                {"tname": table_name},
            ).fetchone()
            if not table_exists:
                continue

            existing_cols = {
                row[1]
                for row in conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            }

            for col_name, col_def in columns.items():
                if col_name not in existing_cols:
                    logger.info(f"[*] Migrating {table_name} table: adding column '{col_name}'")
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"))
        conn.commit()
