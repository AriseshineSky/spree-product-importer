import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from spree_product_importer.config import get_config

_engine = None
_SessionLocal = None


class Base(DeclarativeBase):
    pass


def build_pg_url(cfg: dict) -> str:
    env_url = os.getenv("PG_DATABASE_URL") or os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    if cfg.get("url"):
        return cfg["url"]

    host = cfg.get("host", "localhost")
    port = cfg.get("port", "5432")
    user = cfg["user"]
    password = cfg["password"]
    name = cfg["name"]
    driver = cfg.get("driver", "psycopg")

    return f"postgresql+{driver}://{user}:{password}@{host}:{port}/{name}"


def get_engine():
    global _engine
    if _engine is None:
        config = get_config()
        pg_db = config.get("pg_db")
        if not pg_db:
            raise RuntimeError(
                "PostgreSQL config not found. Add a [pg_db] section "
                "to your ini file or set PG_DATABASE_URL."
            )
        _engine = create_engine(
            build_pg_url(pg_db),
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
        )
    return _SessionLocal


def get_session() -> Session:
    return get_session_factory()()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
