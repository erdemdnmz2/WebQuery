"""
Tests for `masked_columns_in`, which backs `SQLResponse.masked_columns`.

The field exists so a client can show a "masked" affordance based on what the
server actually did rather than on what the client asked for. Those two differ:
a database admin bypasses masking entirely, and a requested column may not be
present in the result set at all. See SPEC-0012 BR-03/BR-04.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from common.security import mask_result_set, masked_columns_in


ROWS = [
    {"CustomerID": 1, "FirstName": "Orlando", "LastName": "Gee", "CompanyName": "A Bike Store"},
    {"CustomerID": 2, "FirstName": "Keith", "LastName": "Harris", "CompanyName": "Progressive Sports"},
]


def test_reports_masked_columns_with_result_set_spelling():
    """Rules are stored lowercased; the client matches against its headers (AC-06)."""
    assert masked_columns_in(ROWS, {"firstname", "lastname"}) == ["FirstName", "LastName"]


def test_ignores_rules_for_columns_not_selected():
    assert masked_columns_in(ROWS, {"firstname", "phone", "passwordhash"}) == ["FirstName"]


def test_empty_when_no_rules():
    assert masked_columns_in(ROWS, set()) == []


def test_empty_when_no_rows():
    assert masked_columns_in([], {"firstname"}) == []


def test_agrees_with_mask_result_set():
    """Whatever this reports must be exactly what actually got redacted."""
    rules = {"firstname", "lastname"}
    reported = masked_columns_in(ROWS, rules)
    masked = mask_result_set(ROWS, rules)

    actually_masked = [name for name in masked[0] if masked[0][name] == "********"]
    assert reported == actually_masked
    for name in ROWS[0]:
        if name not in reported:
            assert masked[0][name] == ROWS[0][name]


def test_none_values_are_reported_even_though_left_alone():
    """mask_result_set skips None; the column is still governed by a rule."""
    rows = [{"FirstName": None, "CompanyName": "A Bike Store"}]
    assert masked_columns_in(rows, {"firstname"}) == ["FirstName"]
    assert mask_result_set(rows, {"firstname"})[0]["FirstName"] is None
