"""Apply immutable PostgreSQL migrations in lexical filename order.

DATABASE_URL is intentionally read from the environment; this script never logs it.
"""

import hashlib
import os
import sys
from pathlib import Path


def migration_checksum(contents: str) -> str:
    return hashlib.sha256(contents.encode("utf-8")).hexdigest()


def configured_database_url() -> str | None:
    """Read DATABASE_URL from the environment, then the ignored backend/.env file."""
    if value := os.environ.get("DATABASE_URL"):
        return value
    env_file = Path(__file__).parent.parent / "backend" / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def main() -> int:
    database_url = configured_database_url()
    if not database_url:
        print("DATABASE_URL must be set.", file=sys.stderr)
        return 2

    try:
        import psycopg
    except ImportError:
        print("Install backend dependencies before running migrations.", file=sys.stderr)
        return 2

    migrations_dir = Path(__file__).parent / "migrations"
    migrations = sorted(migrations_dir.glob("*.sql"))
    if not migrations:
        print("No migration files found.", file=sys.stderr)
        return 2

    psycopg_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(psycopg_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        connection.commit()

        for path in migrations:
            contents = path.read_text(encoding="utf-8")
            checksum = migration_checksum(contents)
            with connection.cursor() as cursor:
                cursor.execute("SELECT checksum FROM schema_migrations WHERE filename = %s", (path.name,))
                existing = cursor.fetchone()
                if existing:
                    if existing[0] != checksum:
                        raise RuntimeError(f"Applied migration changed: {path.name}")
                    print(f"already applied: {path.name}")
                    continue
                cursor.execute(contents)
                cursor.execute(
                    "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)",
                    (path.name, checksum),
                )
            connection.commit()
            print(f"applied: {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
