"""Camada de acesso PostgreSQL/PostGIS do NAPI GeoAI."""

from geoai.db.backup import create_backup, verify_restore
from geoai.db.config import DatabaseConfig, load_dotenv_file, require_database_url
from geoai.db.doctor import run_doctor
from geoai.db.migrate import apply_migrations, list_pending_migrations
from geoai.db.postgis import configure_search_path, resolve_postgis_schema
from geoai.db.security_audit import run_security_audit
from geoai.db.url_safety import redact_database_url

__all__ = [
    "DatabaseConfig",
    "apply_migrations",
    "configure_search_path",
    "create_backup",
    "list_pending_migrations",
    "load_dotenv_file",
    "redact_database_url",
    "require_database_url",
    "resolve_postgis_schema",
    "run_doctor",
    "run_security_audit",
    "verify_restore",
]
