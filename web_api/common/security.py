"""
Security Utilities Module
Contains helpers for dynamic data masking and secure credential generation.
"""
import secrets
import string
from typing import List, Dict, Any, Set

def generate_secure_credentials() -> tuple[str, str]:
    """
    Generates a secure random database username and a strong 32-character password.
    
    Returns:
        tuple[str, str]: (username, password)
    """
    # Generate unique 8-character hex suffix for username
    suffix = secrets.token_hex(4)
    username = f"webquery_user_{suffix}"
    
    # Generate strong 32-character password
    alphabet = string.ascii_letters + string.digits + "!@#$%^*()-_=+"
    password = "".join(secrets.choice(alphabet) for _ in range(32))
    
    return username, password

def mask_result_set(data: List[Dict[str, Any]], mask_columns: Set[str]) -> List[Dict[str, Any]]:
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
                masked_val = "********"
            else:
                masked_val = val
                
            masked_row[col_name] = masked_val
        masked_data.append(masked_row)
        
    return masked_data
