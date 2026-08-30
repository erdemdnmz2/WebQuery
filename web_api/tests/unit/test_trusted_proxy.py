"""
Regression tests for real client IP resolution behind a reverse proxy (P0-4).

nginx forwarded `X-Forwarded-For`, but nothing in the application read it, so
`request.client.host` was the proxy container's address on every request. The
login throttle's per-IP bucket, slowapi's rate limit key and every audit
`client_ip` therefore shared one value: five failed logins anywhere locked the
entire platform out, and the audit trail identified nobody.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from middlewares.proxy_middleware import (
    TrustedProxyMiddleware,
    parse_trusted_proxies,
    resolve_client_ip,
)

NGINX = "172.18.0.5"
TRUSTED = parse_trusted_proxies("172.18.0.0/16")


def test_wildcard_is_never_trusted():
    """'*' would let any client forge its own address."""
    assert parse_trusted_proxies("*") == []
    assert parse_trusted_proxies("*, 10.0.0.1") == parse_trusted_proxies("10.0.0.1")


def test_malformed_entries_are_dropped_without_widening_trust():
    networks = parse_trusted_proxies("10.0.0.1, not-an-ip, 192.168.1.0/24")
    assert len(networks) == 2


def test_client_ip_comes_from_forwarded_header_behind_a_trusted_proxy():
    assert resolve_client_ip(NGINX, "203.0.113.7", TRUSTED) == "203.0.113.7"


def test_two_clients_behind_the_proxy_get_distinct_addresses():
    """The defect: both used to resolve to the proxy's own IP."""
    first = resolve_client_ip(NGINX, "203.0.113.7", TRUSTED)
    second = resolve_client_ip(NGINX, "198.51.100.22", TRUSTED)
    assert first != second


def test_untrusted_peer_header_is_ignored():
    """A client talking to the app directly cannot claim someone else's address."""
    assert resolve_client_ip("203.0.113.9", "10.0.0.1", TRUSTED) == "203.0.113.9"


def test_spoofed_prefix_in_the_chain_is_not_believed():
    """The leftmost entry is client-controlled; the rightmost untrusted hop is not."""
    forwarded = "1.2.3.4, 203.0.113.7"
    assert resolve_client_ip(NGINX, forwarded, TRUSTED) == "203.0.113.7"


def test_trusted_hops_are_skipped_from_the_right():
    forwarded = "203.0.113.7, 172.18.0.9"
    assert resolve_client_ip(NGINX, forwarded, TRUSTED) == "203.0.113.7"


def test_missing_header_falls_back_to_the_peer():
    assert resolve_client_ip(NGINX, None, TRUSTED) == NGINX
    assert resolve_client_ip(NGINX, "", TRUSTED) == NGINX


def test_no_trusted_proxies_configured_leaves_the_peer_untouched():
    assert resolve_client_ip(NGINX, "203.0.113.7", []) == NGINX


def test_ipv6_literal_with_port_is_parsed():
    assert resolve_client_ip(NGINX, "[2001:db8::1]:51234", TRUSTED) == "2001:db8::1"


def test_garbage_hop_is_skipped():
    assert resolve_client_ip(NGINX, "not-an-ip, 203.0.113.7", TRUSTED) == "203.0.113.7"


@pytest.mark.asyncio
async def test_middleware_rewrites_scope_client_and_scheme():
    seen = {}

    async def app(scope, _receive, _send):
        seen["client"] = scope["client"]
        seen["scheme"] = scope["scheme"]

    middleware = TrustedProxyMiddleware(app, trusted_proxies="172.18.0.0/16")
    await middleware(
        {
            "type": "http",
            "scheme": "http",
            "client": (NGINX, 40000),
            "headers": [
                (b"x-forwarded-for", b"203.0.113.7"),
                (b"x-forwarded-proto", b"https"),
            ],
        },
        None,
        None,
    )

    assert seen["client"][0] == "203.0.113.7"
    assert seen["scheme"] == "https"


@pytest.mark.asyncio
async def test_middleware_is_inert_without_configuration():
    seen = {}

    async def app(scope, _receive, _send):
        seen["client"] = scope["client"]

    middleware = TrustedProxyMiddleware(app, trusted_proxies="")
    await middleware(
        {
            "type": "http",
            "scheme": "http",
            "client": (NGINX, 40000),
            "headers": [(b"x-forwarded-for", b"203.0.113.7")],
        },
        None,
        None,
    )

    assert seen["client"][0] == NGINX
