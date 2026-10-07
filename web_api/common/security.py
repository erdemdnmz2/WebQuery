"""
Security Utilities Module
Contains helpers for dynamic data masking.
"""
from collections.abc import Iterable
from typing import Any

# The only masking strategy the engine implements. The column model stores a
# `masking_type` and the admin UI offers it, so the value is validated rather
# than ignored: a rule the engine cannot honour must be refused at write time,
# not silently downgraded at read time. See OQ-2026-013 / ADR-0018.
MASKING_TYPE_FULL = "full"
SUPPORTED_MASKING_TYPES = frozenset({MASKING_TYPE_FULL})
MASK_PLACEHOLDER = "********"


def _table_matches(rule_table: str, referenced: frozenset[str] | set[str]) -> bool:
    """Whether a rule's table is among the tables the query actually reads.

    A rule may be stored schema-qualified (`dbo.Customers`) while the query
    names the table bare, or the other way round; both spellings of every
    referenced table are collected by the planner, and the rule is compared on
    its own bare name too.
    """
    name = rule_table.strip().lower()
    if not name:
        # A rule with no table is legacy data: it predates table scoping and
        # keeps applying everywhere rather than silently switching off.
        return True
    if name in referenced:
        return True
    bare = name.rsplit(".", 1)[-1]
    return bare in referenced


def columns_to_mask(rules: Iterable[Any], referenced_tables: frozenset[str] | set[str]) -> set[str]:
    """Resolve stored masking rules against the tables one query references.

    Enforcement used to drop `table_name` entirely and collect every rule's
    column into one set, so a rule written for `Customers.email` also blanked
    `Suppliers.email` — over-masking that looks like missing data and is
    invisible to the user. Scoping by the query's own tables keeps a rule where
    its author put it.

    Note the residual ambiguity: a result set carries column names, not the
    table each column came from. When a query joins two tables that both have
    an `email` column and only one is ruled, both are masked. That is the
    conservative direction (over-mask rather than leak) and it is the reason
    this resolves against the *query's* tables instead of the whole catalogue.
    """
    referenced = {name.lower() for name in referenced_tables}
    return {
        rule.column_name.lower()
        for rule in rules
        if getattr(rule, "column_name", None)
        and _table_matches(getattr(rule, "table_name", "") or "", referenced)
    }


def mask_result_set(data: list[dict[str, Any]], mask_columns: set[str]) -> list[dict[str, Any]]:
    """
    Masks sensitive columns in query results for non-admin users.
    
    Args:
        data: The query result rows as a list of dictionaries.
        mask_columns: A set of column names (lowercase) that should be masked.
        
    Returns:
        List[Dict[str, Any]]: The masked result set.
    """
    if not data or not mask_columns:
        return data
        
    # Convert mask columns to lowercase for case-insensitive matching
    lower_mask_cols = {col.lower() for col in mask_columns}
    
    masked_data = []
    for row in data:
        masked_row = {}
        for col_name, val in row.items():
            col_lower = col_name.lower()
            
            if col_lower in lower_mask_cols and val is not None:
                masked_val = MASK_PLACEHOLDER
            else:
                masked_val = val
                
            masked_row[col_name] = masked_val
        masked_data.append(masked_row)
        
    return masked_data


def masked_columns_in(data: list[dict[str, Any]], mask_columns: set[str]) -> list[str]:
    """
    Reports which columns `mask_result_set` actually masks for this result set.

    Matching mirrors `mask_result_set`: case-insensitive, but the names are
    returned with the spelling they carry in the result rows so the caller can
    line them up with the column headers it renders.

    Args:
        data: The query result rows as a list of dictionaries.
        mask_columns: A set of column names that should be masked.

    Returns:
        list[str]: Column names present in the result set that are masked.
    """
    if not data or not mask_columns:
        return []

    lower_mask_cols = {col.lower() for col in mask_columns}
    return [name for name in data[0] if name.lower() in lower_mask_cols]
