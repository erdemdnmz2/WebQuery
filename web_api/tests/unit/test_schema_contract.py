"""The schema contract must stay identical to what the models declare.

`common/schema_contract.py` is hand-written plain data, because migrations must
not import model classes. That leaves one failure mode: a model gains an index
and the contract does not, so the startup guard stops noticing the drift it
exists to catch. These tests close that gap by comparing the two directly.
"""
import pytest
import sqlalchemy as sa

from app_database.models import Base
from common.schema_contract import (
    REQUIRED_INDEXES,
    REQUIRED_NOT_NULL,
    REQUIRED_UNIQUE,
    missing_objects,
)


def _model_indexes() -> set[tuple[str, str, tuple[str, ...], bool]]:
    return {
        (index.name, table.name, tuple(c.name for c in index.columns), bool(index.unique))
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }


def _model_unique() -> set[tuple[str, frozenset[str]]]:
    return {
        (table.name, frozenset(c.name for c in constraint.columns))
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }


def _model_not_null() -> set[tuple[str, str]]:
    return {
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if not column.nullable and not column.primary_key
    }


def test_required_indexes_match_the_models():
    contract = {
        (spec.name, spec.table, spec.columns, spec.unique) for spec in REQUIRED_INDEXES
    }
    assert contract == _model_indexes()


def test_required_unique_constraints_match_the_models():
    contract = {(spec.table, frozenset(spec.columns)) for spec in REQUIRED_UNIQUE}
    assert contract == _model_unique()


def test_required_not_null_matches_the_models():
    assert set(REQUIRED_NOT_NULL) == _model_not_null()


@pytest.fixture
def schema_engine():
    """A throwaway database carrying the full model schema."""
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_a_complete_schema_reports_nothing_missing(schema_engine):
    with schema_engine.connect() as connection:
        assert missing_objects(sa.inspect(connection)) == []


def test_a_dropped_index_is_reported(schema_engine):
    with schema_engine.begin() as connection:
        connection.execute(sa.text("DROP INDEX ix_ActionLogging_trace_id"))

    with schema_engine.connect() as connection:
        missing = missing_objects(sa.inspect(connection))

    assert missing == ["index eksik: ix_ActionLogging_trace_id (ActionLogging.trace_id)"]


def test_a_missing_table_is_reported_once_not_as_every_index(schema_engine):
    with schema_engine.begin() as connection:
        connection.execute(sa.text("DROP TABLE MaskingRules"))

    with schema_engine.connect() as connection:
        missing = missing_objects(sa.inspect(connection))

    assert "tablo eksik: MaskingRules" in missing
    assert not any("ix_MaskingRules_id" in item for item in missing)
