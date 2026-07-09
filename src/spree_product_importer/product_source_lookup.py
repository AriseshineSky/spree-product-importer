from collections.abc import Iterable, Sequence

from sqlalchemy import Column, MetaData, String, Table, select, tuple_

from spree_product_importer.config import get_config
from spree_product_importer.database import session_scope

_metadata = MetaData()
_table_cache: dict[str, Table] = {}


def product_source_key(prod: dict) -> tuple[str, str] | None:
    source = prod.get("source")
    source_product_id = prod.get("source_product_id") or prod.get("product_id")
    if not source or source_product_id is None or str(source_product_id) == "":
        return None
    return str(source), str(source_product_id)


def get_product_sources_table_name() -> str:
    config = get_config()
    pg_db = config.get("pg_db") or {}
    return pg_db.get("product_sources_table", "product_sources")


def _product_sources_table() -> Table:
    table_name = get_product_sources_table_name()
    if table_name not in _table_cache:
        _table_cache[table_name] = Table(
            table_name,
            _metadata,
            Column("source", String),
            Column("source_product_id", String),
        )
    return _table_cache[table_name]


class ProductSourceLookup:
    CHUNK_SIZE = 500

    def find_existing(self, keys: Iterable[tuple[str, str]]) -> set[tuple[str, str]]:
        unique_keys = list(dict.fromkeys((source, str(source_product_id)) for source, source_product_id in keys))
        if not unique_keys:
            return set()

        table = _product_sources_table()
        existing: set[tuple[str, str]] = set()

        with session_scope() as session:
            for offset in range(0, len(unique_keys), self.CHUNK_SIZE):
                chunk: Sequence[tuple[str, str]] = unique_keys[offset : offset + self.CHUNK_SIZE]
                stmt = select(table.c.source, table.c.source_product_id).where(
                    tuple_(table.c.source, table.c.source_product_id).in_(chunk)
                )
                for row in session.execute(stmt):
                    existing.add((row.source, row.source_product_id))

        return existing
