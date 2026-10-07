"""
Rate Limiter Configuration Module
Defines a central, shared Limiter instance to be used across all routers.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Define a shared limiter instance
limiter: Limiter = Limiter(key_func=get_remote_address)
