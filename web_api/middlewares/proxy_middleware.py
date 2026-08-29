"""Resolve the real client IP when the application runs behind a reverse proxy.

nginx forwards `X-Forwarded-For` and `X-Forwarded-Proto`, but nothing read them:
`request.client.host` was the proxy's own container IP on *every* request. Three
mechanisms silently collapsed onto that single value:

* `RedisLoginThrottle`'s IP bucket — five failed logins anywhere locked the
  whole platform out for the block window (a self-DoS, made worse by the
  fail-closed decision in OQ-2026-005),
* slowapi's `get_remote_address` — the per-IP rate limits became global,
* `client_ip` on `ActionLogging`, `AuditLog` and `LoginLogging` — every audit
  row carried the same constant, so the actor trail was worthless.

The trusted proxy list is explicit configuration (`TRUSTED_PROXY_IPS`). A header
is only honoured when the *immediate peer* is a trusted proxy, so a client that
sends its own `X-Forwarded-For` directly to the application cannot forge an
address. `*` is rejected: it would make the header trivially spoofable.

See SPEC-0023 / ADR-0020.
"""
import ipaddress
import logging
import os

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


def parse_trusted_proxies(raw: str | None) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Parse a comma-separated list of trusted proxy addresses or CIDR blocks.

    A bare address is treated as a single-host network. Unparseable entries are
    dropped with a warning rather than taking startup down: an operator typo
    must not be able to widen trust, and the resulting empty list simply means
    no header is honoured.
    """
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for item in (raw or "").split(","):
        candidate = item.strip()
        if not candidate:
            continue
        if candidate == "*":
            logger.error(
                "TRUSTED_PROXY_IPS='*' kabul edilmiyor: her istemci kendi IP'sini "
                "sahteleyebilirdi. Girdi yok sayıldı."
            )
            continue
        try:
            networks.append(ipaddress.ip_network(candidate, strict=False))
        except ValueError:
            logger.warning(
                "TRUSTED_PROXY_IPS içindeki '%s' geçerli bir IP/CIDR değil; yok sayıldı.",
                candidate,
            )
    return networks


def _is_trusted(address: str, networks) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(parsed in network for network in networks)


def resolve_client_ip(peer: str | None, forwarded_for: str | None, networks) -> str | None:
    """Return the client address implied by `X-Forwarded-For`, or the peer.

    The chain is walked from the **right**, skipping entries that are themselves
    trusted proxies. The first non-trusted address is the closest hop the
    infrastructure actually vouches for. Reading the leftmost entry instead
    would take whatever the client typed.
    """
    if not peer or not networks or not _is_trusted(peer, networks):
        # Direct connection, or a peer we do not vouch for: the header is
        # attacker-controlled and must be ignored.
        return peer

    hops = [hop.strip() for hop in (forwarded_for or "").split(",") if hop.strip()]
    for hop in reversed(hops):
        # A bracketed IPv6 literal may carry a port: [::1]:443
        candidate = hop
        if candidate.startswith("[") and "]" in candidate:
            candidate = candidate[1 : candidate.index("]")]
        if not _is_trusted(candidate, networks):
            try:
                ipaddress.ip_address(candidate)
            except ValueError:
                continue
            return candidate

    # Every hop was a trusted proxy (or the header was absent): the peer is the
    # best answer available.
    return peer


class TrustedProxyMiddleware:
    """Rewrite `scope["client"]` and `scope["scheme"]` from forwarded headers."""

    def __init__(self, app: ASGIApp, trusted_proxies: str | None = None) -> None:
        self.app = app
        raw = trusted_proxies if trusted_proxies is not None else os.getenv("TRUSTED_PROXY_IPS", "")
        self.networks = parse_trusted_proxies(raw)
        if self.networks:
            logger.info(
                "Güvenilen proxy ağı sayısı: %d; istemci IP'si X-Forwarded-For'dan çözülecek",
                len(self.networks),
            )
        else:
            logger.warning(
                "TRUSTED_PROXY_IPS tanımlı değil. Uygulama bir reverse proxy arkasındaysa "
                "giriş kısıtlaması, rate limit ve audit kayıtları tek bir IP'ye düşer."
            )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.networks:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        peer = client[0] if client else None
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}

        resolved = resolve_client_ip(peer, headers.get("x-forwarded-for"), self.networks)
        if resolved and resolved != peer:
            port = client[1] if client and len(client) > 1 else 0
            scope["client"] = (resolved, port)

        if peer and _is_trusted(peer, self.networks):
            forwarded_proto = headers.get("x-forwarded-proto")
            if forwarded_proto:
                scope["scheme"] = forwarded_proto.split(",")[0].strip()

        await self.app(scope, receive, send)
