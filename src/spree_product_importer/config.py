import os
from pathlib import Path

from cmutils.config_loaders import IniConfigLoader

CONFIG_PATH_ENV = "SPREE_PRODUCT_IMPORTER_CONFIG"
LEGACY_CONFIG_PATH_ENV = "MWS_COLLECTOR_CONFIGURATION_PATH"

_cfg = None


def resolve_config_path() -> str:
    for env_name in (CONFIG_PATH_ENV, LEGACY_CONFIG_PATH_ENV):
        env_path = os.getenv(env_name)
        if env_path:
            path = Path(env_path).expanduser().resolve()
            if path.is_file():
                return str(path)

    default_path = Path("~/.em_celery/config.ini").expanduser().resolve()
    if default_path.is_file():
        return str(default_path)

    cwd = Path.cwd()
    for file_name in ("config_local.ini", "config.ini", "config.sample.ini"):
        path = cwd / file_name
        if path.is_file():
            return str(path)

    app_root = Path(__file__).resolve().parents[2]
    for file_name in ("config_local.ini", "config.ini", "config.sample.ini"):
        path = app_root / file_name
        if path.is_file():
            return str(path)

    raise RuntimeError(
        "Configuration file not found. Set SPREE_PRODUCT_IMPORTER_CONFIG "
        "or create ~/.em_celery/config.ini."
    )


def get_config():
    global _cfg
    if _cfg is None:
        config = IniConfigLoader(resolve_config_path(), interpolation=False)
        _cfg = config.load()
    return _cfg


def init_db():
    from em_tasks.store.models import init_store

    config = get_config()
    db = config["store_db"]
    init_store(db["host"], db["user"], db["password"], db["name"])


def init_pg_db():
    """Initialize SQLAlchemy engine for PostgreSQL ([pg_db] section)."""
    from spree_product_importer.database import get_engine

    get_engine()
