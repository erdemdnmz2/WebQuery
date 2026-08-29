"""
Tests for table-scoped masking rule resolution (P2-6, OQ-2026-013).

Rules are stored as (table_name, column_name, masking_type) and the admin UI
picks them table by table, but enforcement dropped the table entirely and
collected every rule's column into one set. A rule written for `Customers.email`
therefore also blanked `Suppliers.email` — over-masking that looks to the user
like missing data, with nothing anywhere saying it happened.
"""
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from common.security import (
    MASKING_TYPE_FULL,
    SUPPORTED_MASKING_TYPES,
    columns_to_mask,
)
from query_execution.query_analyzer import QueryAnalyzer

ANALYZER = QueryAnalyzer()


@dataclass
class Rule:
    table_name: str
    column_name: str
    masking_type: str = MASKING_TYPE_FULL
    is_active: bool = True


def tables_of(query: str, technology: str = "postgresql"):
    return ANALYZER.plan(query, technology=technology).tables


def test_rule_applies_to_its_own_table():
    rules = [Rule("Customers", "email")]
    assert columns_to_mask(rules, tables_of("SELECT email FROM Customers")) == {"email"}


def test_rule_does_not_leak_onto_another_table():
    """The defect: Customers.email used to mask Suppliers.email too."""
    rules = [Rule("Customers", "email")]
    assert columns_to_mask(rules, tables_of("SELECT email FROM Suppliers")) == set()


def test_schema_qualified_rule_matches_a_bare_table_reference():
    rules = [Rule("dbo.Customers", "email")]
    assert columns_to_mask(rules, tables_of("SELECT email FROM Customers")) == {"email"}


def test_bare_rule_matches_a_schema_qualified_reference():
    rules = [Rule("Customers", "email")]
    assert columns_to_mask(rules, tables_of("SELECT email FROM dbo.Customers")) == {"email"}


def test_matching_is_case_insensitive():
    rules = [Rule("CUSTOMERS", "Email")]
    assert columns_to_mask(rules, tables_of("select email from customers")) == {"email"}


def test_join_masks_only_the_ruled_table_column():
    rules = [Rule("Employees", "salary")]
    query = "SELECT e.salary, d.name FROM Employees e JOIN Departments d ON d.id = e.dept_id"
    assert columns_to_mask(rules, tables_of(query)) == {"salary"}


def test_join_with_both_tables_ruled_masks_both_columns():
    rules = [Rule("Employees", "salary"), Rule("Departments", "budget")]
    query = "SELECT e.salary, d.budget FROM Employees e JOIN Departments d ON d.id = e.dept_id"
    assert columns_to_mask(rules, tables_of(query)) == {"salary", "budget"}


def test_subquery_tables_are_in_scope():
    rules = [Rule("Employees", "salary")]
    query = "SELECT * FROM (SELECT salary FROM Employees) sub"
    assert columns_to_mask(rules, tables_of(query)) == {"salary"}


def test_cte_tables_are_in_scope():
    rules = [Rule("Employees", "salary")]
    query = "WITH e AS (SELECT salary FROM Employees) SELECT salary FROM e"
    assert columns_to_mask(rules, tables_of(query)) == {"salary"}


def test_legacy_rule_without_a_table_still_applies_everywhere():
    """Pre-scoping rows must not switch themselves off silently."""
    rules = [Rule("", "email")]
    assert columns_to_mask(rules, tables_of("SELECT email FROM Anything")) == {"email"}


def test_only_full_masking_is_supported():
    """The stored type is validated at write time rather than ignored at read time."""
    assert SUPPORTED_MASKING_TYPES == frozenset({"full"})
    assert MASKING_TYPE_FULL == "full"
