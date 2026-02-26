"""
Startup initializer for Railway persistent volume.

Runs BEFORE gunicorn on every deploy. Seeds the DATA_DIR volume with:
  - curriculum.db  (copied from the Docker image's /app/seed_curriculum.db on first boot)
  - teachers.db    (created with schema if missing)

On subsequent deploys the existing volume data is left untouched, so teacher
accounts and any curriculum edits survive redeployments.
"""

import os
import shutil
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("init_data")

DATA_DIR = os.getenv("DATA_DIR", ".")
SEED_CURRICULUM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_curriculum.db")
CURRICULUM_TARGET = os.path.join(DATA_DIR, "curriculum.db")
TEACHERS_TARGET = os.path.join(DATA_DIR, "teachers.db")


def ensure_data_dir():
    """Create DATA_DIR if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    logger.info(f"DATA_DIR = {DATA_DIR}")


def seed_curriculum_db():
    """Copy the seed curriculum DB into the volume if it doesn't already exist."""
    if os.path.exists(CURRICULUM_TARGET):
        logger.info(f"curriculum.db already exists at {CURRICULUM_TARGET} — skipping seed.")
        return

    if os.path.exists(SEED_CURRICULUM):
        shutil.copy2(SEED_CURRICULUM, CURRICULUM_TARGET)
        logger.info(f"Seeded curriculum.db from {SEED_CURRICULUM}")
    else:
        # No seed file — create an empty schema
        logger.warning("No seed_curriculum.db found. Initializing empty curriculum database.")
        from curriculum_db import init_curriculum_db
        init_curriculum_db()


def seed_teachers_db():
    """Create the teachers DB with schema if it doesn't exist."""
    if os.path.exists(TEACHERS_TARGET):
        logger.info(f"teachers.db already exists at {TEACHERS_TARGET} — skipping.")
        return

    logger.info(f"Creating teachers.db at {TEACHERS_TARGET}")
    conn = sqlite3.connect(TEACHERS_TARGET)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                school TEXT,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                subject_area TEXT,
                grade_level TEXT,
                years_experience INTEGER,
                bio TEXT
            )
        """)
        conn.commit()
        logger.info("teachers.db schema created.")
    finally:
        conn.close()


if __name__ == "__main__":
    ensure_data_dir()
    seed_curriculum_db()
    seed_teachers_db()
    logger.info("Data initialization complete.")
