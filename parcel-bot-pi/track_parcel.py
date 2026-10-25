#!/usr/bin/env python3
"""
track_parcel.py — parcel tracker for speedposttrack.io

Reproduces the website's own flow (no HTML scraping, no browser):

    GET  /tracking-result?d=<base64>          -> session cookies + risk flags
    POST /api/token                           -> single-use socket token
    Socket.IO (Engine.IO v4, HTTP polling)
        POST 40{"token":...}                  -> namespace connect
        POST 42["track",{trackingNumber,courierId,token}]
        GET  42["trackResult",{...}]

Usage:
    python3 track_parcel.py                     # interactive
    python3 track_parcel.py -c speedpost -t EL836643777IN
    python3 track_parcel.py -c flipkart -t FMPP4392861093 --json
    python3 track_parcel.py -c speedpost -t EL836643777IN --save-csv out.csv

Requires only `requests`.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import requests
except ImportError:  # pragma: no cover
    sys.stderr.write("This script needs `requests`:\n    pip install requests\n")
    raise SystemExit(1)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

BASE_URL = "https://speedposttrack.io"
SOCKET_PATH = "/socket.io/"
TOKEN_PATH = "/api/token"
RESULT_PATH = "/tracking-result"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = 30
POLL_TIMEOUT = 25
DEFAULT_DELAY = 5.0          # seconds between upstream lookups
MAX_RETRIES = 3
CACHE_TTL = 600              # 10 minutes
CACHE_DIR = Path(
    os.environ.get("TRACKER_CACHE_DIR", Path.home() / ".cache" / "speedposttrack")
)

WIDTH = 64

# Ordered courier catalogue. `detect` mirrors the site's detection priorities.
COURIERS: List[Dict[str, Any]] = [
    {"id": "speedpost", "name": "India Post Speed Post", "short": "Speed Post",
     "rx": r"^[A-Z]{2}\d{9}[A-Z]{2}$", "desc": "2 letters + 9 digits + 2 letters",
     "sample": "EL836643777IN", "currency": "\u20b9", "detect": 9},
    {"id": "bluedart", "name": "BlueDart Express", "short": "BlueDart",
     "rx": r"^\d{11}$", "desc": "11 digits",
     "sample": "12345678901", "currency": "\u20b9", "detect": 5},
    {"id": "delhivery", "name": "Delhivery", "short": "Delhivery",
     "rx": r"^\d{12,18}$", "desc": "12-18 digits",
     "sample": "123456789012", "currency": "\u20b9", "detect": 7},
    {"id": "flipkart", "name": "Flipkart Shipping", "short": "Flipkart",
     "rx": r"^[A-Z]{4}\d{10}$", "desc": "4 letters + 10 digits",
     "sample": "FMPP4392861093", "currency": "\u20b9", "detect": 0},
    {"id": "dtdc", "name": "DTDC Courier", "short": "DTDC",
     "rx": r"^[A-Z0-9\-]{8,32}$", "desc": "8-32 letters/digits/-",
     "sample": "D12345678", "currency": "\u20b9", "detect": 999},
    {"id": "ekart", "name": "Ekart Logistics", "short": "Ekart",
     "rx": r"^[A-Z]{4}\d{10}$", "desc": "4 letters + 10 digits",
     "sample": "FMPP4392861093", "currency": "\u20b9", "detect": 6},
    {"id": "xpressbees", "name": "XpressBees", "short": "XpressBees",
     "rx": r"^\d{13,15}$", "desc": "13-15 digits",
     "sample": "1234567890123", "currency": "\u20b9", "detect": 0},
    {"id": "valmo", "name": "Valmo", "short": "Valmo",
     "rx": r"^VL\d{13}$", "desc": "VL + 13 digits",
     "sample": "VL1234567890123", "currency": "\u20b9", "detect": 0},
    {"id": "shadowfax", "name": "Shadowfax", "short": "Shadowfax",
     "rx": r"^(?:SF|R)\d+[A-Z]+$", "desc": "SF/R + digits + letters",
     "sample": "SF1234567890A", "currency": "\u20b9", "detect": 12},
    {"id": "myntra", "name": "Myntra", "short": "Myntra",
     "rx": r"^[A-Z]{4}\d{10}$", "desc": "4 letters + 10 digits",
     "sample": "MYNT1234567890", "currency": "\u20b9", "detect": 4},
    {"id": "safexpress", "name": "Safexpress", "short": "Safexpress",
     "rx": r"^\d{12}$", "desc": "12 digits",
     "sample": "123456789012", "currency": "\u20b9", "detect": 0},
    {"id": "saudipost", "name": "Saudi Post", "short": "SPL",
     "rx": r"^ABSEPS\d{10}$", "desc": "ABSEPS + 10 digits",
     "sample": "ABSEPS1234567890", "currency": "SAR ", "detect": 8},
    {"id": "emiratespost", "name": "Emirates Post", "short": "Emirates",
     "rx": r"^EE\d{9}AE$", "desc": "EE + 9 digits + AE",
     "sample": "EE123456789AE", "currency": "AED ", "detect": 1},
    {"id": "omanpost", "name": "Oman Post", "short": "Oman",
     "rx": r"^EE\d{9}OM$", "desc": "EE + 9 digits + OM",
     "sample": "EE123456789OM", "currency": "OMR ", "detect": 2},
]

# The site's own menu order (first five are the ones the user asked for).
MENU_IDS = ["speedpost", "bluedart", "delhivery", "flipkart", "dtdc"]

BY_ID = {c["id"]: c for c in COURIERS}


# --------------------------------------------------------------------------- #
# Terminal helpers
# --------------------------------------------------------------------------- #

_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def paint(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def bold(t: str) -> str:
    return paint(t, "1")


def dim(t: str) -> str:
    return paint(t, "2")


def green(t: str) -> str:
    return paint(t, "32")


def yellow(t: str) -> str:
    return paint(t, "33")


def red(t: str) -> str:
    return paint(t, "31")


def cyan(t: str) -> str:
    return paint(t, "36")


def rule(char: str = "\u2500", width: int = WIDTH) -> str:
    return dim(char * width)


def section(title: str) -> str:
    head = f"  \u2500\u2500 {title} "
    return cyan(head) + dim("\u2500" * max(0, WIDTH - len(head)))


def truncate(text: str, width: int) -> str:
    text = str(text)
    if len(text) <= width:
        return text
    return text[: max(0, width - 1)] + "\u2026"


def warn(msg: str) -> None:
    sys.stderr.write(yellow(f"  ! {msg}") + "\n")
    sys.stderr.flush()


def info(msg: str) -> None:
    sys.stderr.write(dim(f"  \u00b7 {msg}") + "\n")
    sys.stderr.flush()


def show(value: Any) -> str:
    """Render a value for display; missing values become an em dash."""
    if value is None:
        return "\u2014"
    if isinstance(value, str) and not value.strip():
        return "\u2014"
    return str(value).strip()


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

class TrackerError(Exception):
    exit_code = 1


class NoDataError(TrackerError):
    exit_code = 2


class CaptchaRequired(TrackerError):
    exit_code = 3


class IPBlocked(TrackerError):
    exit_code = 4


class SocketGone(TrackerError):
    pass


class SocketTimeout(TrackerError):
    pass


# --------------------------------------------------------------------------- #
# Socket.IO / Engine.IO v4 client over HTTP long-polling
# --------------------------------------------------------------------------- #

class TrackClient:
    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "*/*",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}{RESULT_PATH}",
            }
        )
        self.sid: Optional[str] = None
        self._pending_token: Optional[str] = None
        self._bootstrap: Optional[Tuple[str, str]] = None  # (number, courier)
        self._delay = DEFAULT_DELAY
        self._last_lookup = 0.0

    # -- low level ---------------------------------------------------------- #

    def _log(self, direction: str, what: str) -> None:
        if self.debug:
            sys.stderr.write(dim(f"    {direction} {what}") + "\n")

    def _poll_url(self) -> str:
        return f"{BASE_URL}{SOCKET_PATH}?EIO=4&transport=polling&sid={self.sid}"

    def _xhr(self) -> Dict[str, str]:
        return {"Accept": "*/*", "Referer": f"{BASE_URL}{RESULT_PATH}"}

    def _post(self, body: str) -> requests.Response:
        self._log("->", f"socket.io POST {body[:110]}")
        r = self.session.post(
            self._poll_url(),
            data=body,
            headers={
                "Accept": "*/*",
                "Content-Type": "text/plain;charset=UTF-8",
                "Referer": f"{BASE_URL}{RESULT_PATH}",
            },
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            raise SocketGone(f"poll POST returned HTTP {r.status_code}: {r.text[:120]}")
        return r

    # -- session bootstrap -------------------------------------------------- #

    def bootstrap(self, number: str, courier: str) -> None:
        """Load /tracking-result?d=… to obtain cookies and risk-control flags."""
        self._bootstrap = (number, courier)
        payload = json.dumps({"t": number, "c": courier}, separators=(",", ":"))
        encoded = base64.b64encode(payload.encode()).decode()

        self._log("->", f"GET {RESULT_PATH}?d={encoded}")
        r = self.session.get(
            f"{BASE_URL}{RESULT_PATH}",
            params={"d": encoded},
            headers={"Accept": "text/html,application/xhtml+xml"},
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            raise TrackerError(f"tracking page returned HTTP {r.status_code}")

        html = r.text
        challenge = _attr(html, "data-trust-challenge")
        blocked = _attr(html, "data-trust-blocked")

        if blocked == "1":
            raise IPBlocked(
                "speedposttrack.io reports this IP as blocked. "
                "Wait a while or use another network."
            )
        if challenge == "1":
            raise CaptchaRequired(
                "The site is asking for a Cloudflare Turnstile challenge.\n"
                "    Open https://speedposttrack.io in a browser, complete the check,\n"
                "    then run this script from the same network shortly after."
            )

        embedded = _attr(html, "data-socket-auth", quote="'")
        token = None
        if embedded and embedded != "null":
            try:
                token = json.loads(embedded).get("token")
            except (ValueError, AttributeError):
                token = None

        if not token:
            token = self.fetch_token()
        self._connect_socket(token)
        # The connect packet does not consume the token, so the first `track`
        # emit can reuse it instead of requesting a second one.
        self._pending_token = token

    def _connect_socket(self, token: str) -> None:
        """Handshake + namespace connect. Keeps the token for the first track."""
        url = f"{BASE_URL}{SOCKET_PATH}"
        params = {"EIO": "4", "transport": "polling", "t": _ms()}
        self._log("->", f"GET {SOCKET_PATH} (handshake)")
        r = self.session.get(
            url, params=params, headers=self._xhr(), timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        text = r.text
        if not text.startswith("0"):
            raise TrackerError(f"unexpected socket handshake: {text[:120]}")
        self.sid = json.loads(text[1:]).get("sid")
        if not self.sid:
            raise TrackerError("socket handshake returned no sid")

        self._post("40" + json.dumps({"token": token}, separators=(",", ":")))
        name, _ = self._poll(want=(), timeout=10, want_connect=True)
        if name != "connect":
            raise SocketGone("socket namespace connect failed")
        self._log("<-", "connected")

    def reconnect(self) -> None:
        self.sid = None
        token = self._pending_token or self.fetch_token()
        self._pending_token = token
        self._connect_socket(token)

    # -- token -------------------------------------------------------------- #

    def fetch_token(self) -> str:
        self._log("->", f"POST {TOKEN_PATH}")
        r = self.session.post(
            f"{BASE_URL}{TOKEN_PATH}",
            json={"turnstileToken": None},
            headers={
                "Accept": "*/*",
                "Referer": f"{BASE_URL}{RESULT_PATH}",
            },
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 403 and "no_page" in r.text:
            if not self._bootstrap:
                raise TrackerError("no tracking page loaded; cannot obtain a token")
            self.bootstrap(*self._bootstrap)
            return self._pending_token or self.fetch_token()
        if r.status_code != 200:
            raise TrackerError(
                f"token request failed: HTTP {r.status_code} {r.text[:120]}"
            )
        try:
            token = r.json()["socketAuth"]["token"]
        except (ValueError, KeyError, TypeError):
            raise TrackerError(f"unexpected token response: {r.text[:160]}")
        self._log("<-", f"token {token[:8]}…")
        return token

    def _next_token(self) -> str:
        if self._pending_token:
            token, self._pending_token = self._pending_token, None
            return token
        return self.fetch_token()

    # -- polling ------------------------------------------------------------ #

    def _poll(
        self,
        want: Iterable[str] = (),
        timeout: float = POLL_TIMEOUT,
        want_connect: bool = False,
    ) -> Tuple[str, Any]:
        want = tuple(want)
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = max(3.0, deadline - time.time())
            try:
                r = self.session.get(
                    self._poll_url(),
                    params={"t": _ms()},
                    headers=self._xhr(),
                    timeout=remaining,
                )
            except requests.Timeout:
                continue

            if r.status_code == 400:
                raise SocketGone(f"poll rejected: {r.text[:120]}")
            if r.status_code != 200:
                raise SocketGone(f"poll returned HTTP {r.status_code}")

            body = r.text
            if not body:
                continue

            for packet in body.split("\x1e"):
                if not packet:
                    continue
                self._log("<-", packet[:110])

                if packet == "2":            # Engine.IO ping
                    self._post("3")          # pong
                    continue
                if packet == "1":            # Engine.IO close
                    raise SocketGone("server closed the socket")
                if packet.startswith("44"):
                    raise SocketGone(f"socket error: {packet[2:][:120]}")
                if packet.startswith("40"):
                    if want_connect:
                        return "connect", json.loads(packet[2:] or "{}")
                    continue
                if packet.startswith("41"):
                    raise SocketGone("namespace disconnected")
                if packet.startswith("42"):
                    try:
                        name, payload = json.loads(packet[2:])
                    except (ValueError, TypeError):
                        continue
                    if name in want:
                        return name, payload

        raise SocketTimeout("no tracking response within the timeout")
        # (unreachable, keeps linters quiet)

    # -- tracking ----------------------------------------------------------- #

    def _pace(self, delay: float) -> None:
        if delay <= 0:
            return
        wait = delay - (time.time() - self._last_lookup)
        if wait > 0:
            info(f"waiting {wait:.0f}s before the next upstream lookup")
            time.sleep(wait)

    def track(self, number: str, courier: str, delay: Optional[float] = None) -> Dict[str, Any]:
        delay = self._delay if delay is None else delay
        self._pace(delay)

        last_error = "unknown error"
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                token = self._next_token()
                body = json.dumps(
                    [
                        "track",
                        {
                            "trackingNumber": number,
                            "courierId": courier,
                            "token": token,
                        },
                    ],
                    separators=(",", ":"),
                )
                self._post("42" + body)
                self._last_lookup = time.time()

                name, payload = self._poll(want=("trackResult", "trackError"))
                if name == "trackResult":
                    return payload

                message = str((payload or {}).get("message") or "tracking failed")
                low = message.lower()
                last_error = message

                if "unauthorized" in low:
                    warn("token rejected, requesting a fresh one")
                    self._pending_token = None
                    continue

                if "rate limit" in low or "too many" in low:
                    wait = 60 * (2 ** (attempt - 1))
                    warn(f"rate limited by the site, backing off {wait}s")
                    time.sleep(wait)
                    self._pending_token = None
                    try:
                        self.reconnect()
                    except TrackerError:
                        pass
                    continue

                if "too many tracking requests" in low:
                    wait = 60 * (2 ** (attempt - 1))
                    warn(f"too many requests, backing off {wait}s")
                    time.sleep(wait)
                    continue

                if " is down" in low or "not configured" in low:
                    raise TrackerError(
                        f"the provider's tracking service is currently unavailable: {message}"
                    )

                if any(
                    marker in low
                    for marker in (
                        "not found",
                        "invalid awb",
                        "invalid tracking",
                        "no tracking details",
                        "no tracking events",
                    )
                ):
                    raise NoDataError(message)

                raise TrackerError(message)

            except SocketGone as exc:
                last_error = str(exc)
                if attempt == MAX_RETRIES:
                    break
                warn(f"socket lost ({exc}), reconnecting")
                time.sleep(2 * attempt)
                try:
                    self.reconnect()
                except TrackerError as inner:
                    last_error = str(inner)
            except SocketTimeout as exc:
                last_error = str(exc)
                if attempt == MAX_RETRIES:
                    break
                warn("timed out waiting for the courier, retrying")
                try:
                    self.reconnect()
                except TrackerError as inner:
                    last_error = str(inner)
            except requests.RequestException as exc:
                last_error = str(exc)
                if attempt == MAX_RETRIES:
                    break
                warn(f"network error ({exc.__class__.__name__}), retrying")
                time.sleep(3 * attempt)
                try:
                    self.reconnect()
                except TrackerError as inner:
                    last_error = str(inner)

        raise TrackerError(f"tracking failed after {MAX_RETRIES} attempts: {last_error}")


def _ms() -> int:
    return int(time.time() * 1000)


def _attr(html: str, name: str, quote: str = '"') -> Optional[str]:
    match = re.search(rf"{name}\s*=\s*{quote}([^{quote}]*){quote}", html)
    return match.group(1) if match else None


# --------------------------------------------------------------------------- #
# Local cache
# --------------------------------------------------------------------------- #

def cache_file(courier: str, number: str) -> Path:
    return CACHE_DIR / f"{courier}_{number}.json"


def cache_read(courier: str, number: str) -> Optional[Dict[str, Any]]:
    path = cache_file(courier, number)
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if time.time() - float(blob.get("fetched_at", 0)) > CACHE_TTL:
        return None
    return blob


def cache_write(courier: str, number: str, payload: Dict[str, Any]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file(courier, number).write_text(
            json.dumps({"fetched_at": time.time(), "payload": payload}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Extraction helpers
# --------------------------------------------------------------------------- #

_DATE_OUT = "%d %b %Y"
_DATE_TIME_OUT = "%d %b %Y %H:%M"


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def fmt_date(value: Optional[str]) -> str:
    dt = parse_iso(value)
    return dt.strftime(_DATE_OUT) if dt else show(value)


def fmt_datetime(value: Optional[str]) -> str:
    dt = parse_iso(value)
    return dt.strftime(_DATE_TIME_OUT) if dt else show(value)


def event_datetime(event: Dict[str, Any]) -> datetime:
    """Combine the ISO date (calendar day) with the separate clock field."""
    base = parse_iso(event.get("date"))
    if base is None:
        return datetime.min
    base = base.replace(hour=0, minute=0, second=0, microsecond=0)

    clock = str(event.get("time") or "").strip()
    parts = clock.split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        second = int(parts[2]) if len(parts) > 2 else 0
        return base.replace(hour=hour, minute=minute, second=second)
    except (ValueError, IndexError):
        return base


def event_day(event: Dict[str, Any]) -> str:
    base = parse_iso(event.get("date"))
    return base.strftime(_DATE_OUT) if base else "\u2014"


def event_clock(event: Dict[str, Any]) -> str:
    clock = str(event.get("time") or "").strip()
    if not clock:
        base = parse_iso(event.get("date"))
        return base.strftime("%H:%M") if base else "\u2014"
    return clock


def classify(event: Dict[str, Any]) -> str:
    """booked | dispatched | received | delivered | other"""
    icon = str(event.get("iconClass") or "").lower()
    label = str(event.get("event") or "").lower()
    status = str(event.get("status") or "").lower()

    if "deliver" in label or status == "delivered":
        return "delivered"
    if icon == "pickup" or "book" in label or "created" in label:
        return "booked"
    if icon == "dispatched":
        return "dispatched"
    if icon == "received":
        return "received"
    if "dispatch" in label or "forward" in label:
        return "dispatched"
    if "receiv" in label or "arriv" in label:
        return "received"
    return "other"


KIND_LABEL = {
    "booked": "BOOKED",
    "dispatched": "DISPATCHED",
    "received": "RECEIVED",
    "delivered": "DELIVERED",
    "other": "UPDATE",
}


def sort_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(events, key=event_datetime)


def pretty_article_type(value: Optional[str]) -> str:
    if not value or str(value).upper() == "UNKNOWN":
        return "\u2014"
    return str(value).replace("_", " ").title()


def money(value: Any, symbol: str) -> str:
    if value is None or value == "":
        return "\u2014"
    try:
        return f"{symbol}{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def weight(value: Any) -> str:
    if value is None or value == "":
        return "\u2014"
    text = str(value).strip()
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return f"{text} g"
    return text


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

STATE_STYLE = {
    "delivered": green,
    "out_for_delivery": cyan,
    "in_transit": yellow,
    "rto": red,
    "no_data": dim,
}


def render(payload: Dict[str, Any], courier_id: str, from_cache: bool, fetched_at: float) -> None:
    config = BY_ID.get(courier_id, {"name": courier_id, "currency": "\u20b9"})
    data = payload.get("data") or {}
    booking = data.get("booking_details") or {}
    events = sort_events(list(data.get("tracking_details") or []))
    symbol = config.get("currency", "\u20b9")

    status = show(data.get("overall_status"))
    state = str(data.get("overall_state") or "")
    tint = STATE_STYLE.get(state, lambda t: t)

    print()
    print(rule("\u2550"))
    print("  " + bold("PARCEL TRACKER") + dim(" \u00b7 ") + bold(config["name"]))
    print(rule("\u2550"))

    _kv("Tracking ID", show(payload.get("trackingNumber") or booking.get("article_number")))
    if payload.get("provider"):
        _kv("Provider", show(payload.get("provider")))
    _kv("Status", tint(bold(status)))
    if data.get("del_status"):
        _kv("Delivery", show(data.get("del_status")))
    flags = f"state: {show(state)}"
    if data.get("rto_complete"):
        flags += "   " + red("RTO complete")
    _kv("Flags", dim(flags))
    source = "cache" if from_cache else "live"
    _kv(
        "Fetched",
        f"{datetime.fromtimestamp(fetched_at).strftime(_DATE_TIME_OUT)}  "
        + dim(f"({source})"),
    )

    if events:
        last = events[-1]
        _kv(
            "Last scan",
            f"{event_day(last)} {event_clock(last)} " + dim("\u00b7 ")
            + f"{collapse(show(last.get('office')))} " + dim("\u00b7 ")
            + show(last.get("event")),
        )
    elif state == "no_data":
        _kv("Last scan", dim("no scans yet"))

    # ---- shipment -------------------------------------------------------- #
    print()
    print(section("SHIPMENT"))
    _kv("Article type", pretty_article_type(booking.get("article_type")))
    _kv("Booked on", fmt_datetime(booking.get("booked_on") or booking.get("booking_date")))
    _kv("Weight", weight(booking.get("weight_value")))
    _kv("Tariff", money(booking.get("tariff"), symbol))
    _kv("COD", money(booking.get("cod_amount"), symbol))
    if booking.get("service_type"):
        _kv("Service", show(booking.get("service_type")))
    if booking.get("receiver_name"):
        _kv("Receiver", show(booking.get("receiver_name")))
    if booking.get("merchant_name"):
        _kv("Merchant", show(booking.get("merchant_name")))
    if booking.get("reference_no"):
        _kv("Reference", show(booking.get("reference_no")))
    if booking.get("source_country") or booking.get("destination_country"):
        _kv(
            "Countries",
            f"{show(booking.get('source_country'))} \u2192 {show(booking.get('destination_country'))}",
        )

    # ---- route ----------------------------------------------------------- #
    from_place = (
        booking.get("booked_at")
        or booking.get("origin_city")
        or booking.get("booking_office_name")
    )
    from_pin = booking.get("origin_pincode") or booking.get("booking_pin")
    to_place = (
        booking.get("delivery_location")
        or booking.get("destination_office_name")
        or booking.get("destination_city")
    )
    to_pin = booking.get("destination_pincode")

    print()
    print(section("ROUTE"))
    print("  " + bold("FROM") + "  " + collapse(show(from_place))
          + (dim(f"  ({from_pin})") if from_pin else ""))
    if booking.get("booked_on"):
        print("        " + dim("booked " + fmt_datetime(booking.get("booked_on"))))
    print("    " + dim("\u2502"))
    print("    " + dim("\u25bc"))
    print("  " + bold("TO") + "    " + collapse(show(to_place))
          + (dim(f"  ({to_pin})") if to_pin else ""))

    if booking.get("delivery_confirmed_on"):
        label = "returned " if state == "rto" else "delivered "
        print("        " + dim(label + fmt_datetime(booking.get("delivery_confirmed_on"))))
    elif booking.get("expected_delivery_date"):
        print("        " + dim("ETA " + fmt_date(booking.get("expected_delivery_date"))))

    # ---- hub activity ---------------------------------------------------- #
    dispatched = [e for e in events if classify(e) == "dispatched"]
    received = [e for e in events if classify(e) == "received"]

    if dispatched or received:
        print()
        print(section("HUB ACTIVITY (dispatch / receive)"))
        for title, bucket in (("DISPATCHED", dispatched), ("RECEIVED", received)):
            if not bucket:
                continue
            print("  " + bold(title))
            for event in reversed(bucket):
                office = collapse(show(event.get("office")))
                print(
                    "    "
                    + f"{event_day(event)} {event_clock(event)}"
                    + dim(" \u00b7 ")
                    + f"{truncate(office, 32):<32} "
                    + show(event.get("event"))
                )

    # ---- journey map ----------------------------------------------------- #
    if events:
        print()
        print(section("JOURNEY MAP"))
        header = (
            f"  {'#':>2}  {'DATE':<12} {'TIME':<9} {'HUB':<32} {'ACTION':<24} TYPE"
        )
        print(dim(header))
        for index, event in enumerate(events, start=1):
            print(
                f"  {index:>2}  {event_day(event):<12} {event_clock(event):<9} "
                f"{truncate(collapse(show(event.get('office'))), 32):<32} "
                f"{truncate(show(event.get('event')), 24):<24} "
                f"{KIND_LABEL[classify(event)]}"
            )

    # ---- full timeline --------------------------------------------------- #
    if events:
        print()
        print(section("FULL TIMELINE (oldest \u2192 newest)"))
        for index, event in enumerate(events, start=1):
            print()
            print(
                f"  [{index}] {event_day(event)} {event_clock(event)}  "
                + bold(collapse(show(event.get("office"))))
            )
            detail = show(event.get("event"))
            if event.get("remarks"):
                detail += dim("  \u2014 " + collapse(event["remarks"]))
            print(f"      {detail}  " + dim(f"({KIND_LABEL[classify(event)].lower()})"))
            if event.get("eventcode"):
                print("      " + dim(f"code: {event['eventcode']}"))

    print()
    print(rule("\u2550"))
    print()


def _kv(label: str, value: str) -> None:
    print(f"  {label:<12}: {value}")


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #

def save_json(path: str, payload: Dict[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    info(f"saved JSON \u2192 {path}")


def save_csv(path: str, payload: Dict[str, Any], courier_id: str) -> None:
    data = payload.get("data") or {}
    booking = data.get("booking_details") or {}
    events = sort_events(list(data.get("tracking_details") or []))
    fields = [
        "tracking", "courier", "seq", "date", "time", "office", "officeid",
        "eventcode", "event", "kind", "status", "remarks",
    ]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, event in enumerate(events, start=1):
            writer.writerow(
                {
                    "tracking": payload.get("trackingNumber") or booking.get("article_number") or "",
                    "courier": courier_id,
                    "seq": index,
                    "date": event_day(event),
                    "time": event_clock(event),
                    "office": collapse(show(event.get("office"))),
                    "officeid": event.get("officeid") or "",
                    "eventcode": event.get("eventcode") or "",
                    "event": event.get("event") or "",
                    "kind": classify(event),
                    "status": event.get("status") or "",
                    "remarks": event.get("remarks") or "",
                }
            )
    info(f"saved CSV \u2192 {path} ({len(events)} rows)")


# --------------------------------------------------------------------------- #
# Tracking orchestration
# --------------------------------------------------------------------------- #

def has_data(payload: Dict[str, Any]) -> bool:
    data = payload.get("data") or {}
    if data.get("tracking_details"):
        return True
    booking = data.get("booking_details") or {}
    if booking.get("booked_at") or booking.get("booked_on"):
        return True
    return str(data.get("overall_state") or "") not in ("no_data", "")


def lookup(
    client: TrackClient,
    number: str,
    courier_id: str,
    use_cache: bool,
    refresh: bool,
    delay: float,
) -> Tuple[Dict[str, Any], bool, float]:
    if use_cache and not refresh:
        blob = cache_read(courier_id, number)
        if blob:
            return blob["payload"], True, float(blob["fetched_at"])

    if client.sid is None:
        # One bootstrap (session cookie) is enough for every courier and number;
        # `fetch_token` re-bootstraps automatically if the server disagrees.
        client.bootstrap(number, courier_id)

    payload = client.track(number, courier_id, delay=delay)

    if use_cache:
        cache_write(courier_id, number, payload)

    return payload, False, time.time()


def run_once(args: argparse.Namespace, number: str, courier_id: str, client: TrackClient) -> int:
    config = BY_ID.get(courier_id)
    if not config:
        warn(f"unknown courier id: {courier_id}")
        return 1

    if args.debug:
        info(f"tracking {number} with {courier_id}")

    try:
        payload, from_cache, fetched_at = lookup(
            client,
            number,
            courier_id,
            use_cache=not args.no_cache,
            refresh=args.refresh,
            delay=args.delay,
        )
    except TrackerError as exc:
        warn(str(exc))
        return exc.exit_code

    if not has_data(payload):
        print()
        warn(
            "no tracking details found for this number.\n"
            "    Double-check the ID; freshly booked parcels can take up to 24h to appear."
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        render(payload, courier_id, from_cache, fetched_at)

    if args.save_json:
        save_json(args.save_json, payload)
    if args.save_csv:
        save_csv(args.save_csv, payload, courier_id)

    return 0


# --------------------------------------------------------------------------- #
# Interactive shell
# --------------------------------------------------------------------------- #

def prompt_courier() -> Optional[str]:
    print()
    print("  " + bold("Parcel Tracker") + dim(" \u2014 speedposttrack.io"))
    print("  " + dim("\u2500" * 46))
    for index, courier_id in enumerate(MENU_IDS, start=1):
        config = BY_ID[courier_id]
        print(
            f"  {index}) {config['name']:<24} "
            + dim(f"{config['desc']:<31} ({config['sample']})")
        )
    print("  " + dim("more: ") + ", ".join(
        c["id"] for c in COURIERS if c["id"] not in MENU_IDS
    ))
    print()

    while True:
        try:
            answer = input("  Choose courier [1-5, id, or 'a' to auto-detect]: ").strip()
        except EOFError:
            return None
        if not answer:
            continue
        if answer.lower() in ("q", "quit", "exit"):
            return None
        if answer.lower() == "a":
            return "auto"
        if answer.isdigit():
            index = int(answer)
            if 1 <= index <= len(MENU_IDS):
                return MENU_IDS[index - 1]
            warn("number out of range")
            continue
        if answer.lower() in BY_ID:
            return answer.lower()
        warn(f"unknown courier '{answer}'")


def auto_detect(number: str) -> Optional[str]:
    candidates = sorted(
        (c for c in COURIERS if c["id"] != "dtdc"),
        key=lambda c: c["detect"],
    )
    for config in candidates:
        if re.match(config["rx"], number):
            return config["id"]
    if re.match(BY_ID["dtdc"]["rx"], number):
        return "dtdc"
    return None


def normalize(number: str) -> str:
    return re.sub(r"\s+", "", number).upper()


def validate(number: str, courier_id: str) -> bool:
    return bool(re.match(BY_ID[courier_id]["rx"], number))


def prompt_number(courier_id: str) -> Optional[str]:
    while True:
        try:
            raw = input("  Tracking ID: ").strip()
        except EOFError:
            return None
        if raw.lower() in ("q", "quit", "exit", ""):
            return None

        number = normalize(raw)

        if courier_id == "auto":
            detected = auto_detect(number)
            if not detected:
                warn("could not recognise that ID; pick the courier manually")
                return None
            info(f"detected courier: {BY_ID[detected]['name']}")
            return f"{number}|{detected}"

        if validate(number, courier_id):
            return f"{number}|{courier_id}"

        detected = auto_detect(number)
        if detected and detected != courier_id:
            warn(
                f"'{number}' does not look like a {BY_ID[courier_id]['short']} ID "
                f"({BY_ID[courier_id]['desc']})."
            )
            try:
                answer = input(
                    f"  Use {BY_ID[detected]['name']} instead? [Y/n]: "
                ).strip().lower()
            except EOFError:
                return None
            if answer in ("", "y", "yes"):
                return f"{number}|{detected}"
            continue

        warn(
            f"invalid format for {BY_ID[courier_id]['short']} "
            f"(expected {BY_ID[courier_id]['desc']})"
        )


def interactive(args: argparse.Namespace, client: TrackClient) -> int:
    while True:
        courier_id = prompt_courier()
        if not courier_id:
            return 0

        picked = prompt_number(courier_id)
        if not picked:
            continue
        number, courier_id = picked.split("|", 1)

        code = run_once(args, number, courier_id, client)

        try:
            again = input("  Track another parcel? [Y/n]: ").strip().lower()
        except EOFError:
            return code
        if again in ("n", "no"):
            return code


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Track parcels via speedposttrack.io (same backend the site uses).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 track_parcel.py\n"
            "  python3 track_parcel.py -c speedpost -t EL836643777IN\n"
            "  python3 track_parcel.py -c flipkart -t FMPP4392861093 --json\n"
            "  python3 track_parcel.py -c speedpost -t EL836643777IN --save-csv out.csv\n"
        ),
    )
    parser.add_argument("-c", "--courier", help="courier id (speedpost, flipkart, ...)")
    parser.add_argument("-t", "--tracking", help="tracking number")
    parser.add_argument("--json", action="store_true", help="print raw API payload only")
    parser.add_argument("--save-json", metavar="PATH", help="write raw payload to PATH")
    parser.add_argument("--save-csv", metavar="PATH", help="write timeline rows to PATH")
    parser.add_argument("--refresh", action="store_true", help="ignore the local cache")
    parser.add_argument("--no-cache", action="store_true", help="disable the local cache")
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"seconds between upstream lookups (default {DEFAULT_DELAY:g})",
    )
    parser.add_argument("--debug", action="store_true", help="log HTTP traffic to stderr")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    client = TrackClient(debug=args.debug)

    try:
        if args.courier or args.tracking:
            if not (args.courier and args.tracking):
                warn("both --courier and --tracking are required together")
                return 1

            courier_id = args.courier.lower()
            number = normalize(args.tracking)

            if courier_id not in BY_ID:
                warn(f"unknown courier '{courier_id}'. Known: {', '.join(BY_ID)}")
                return 1
            if not validate(number, courier_id):
                detected = auto_detect(number)
                hint = (
                    f" It looks like a {BY_ID[detected]['name']} ID."
                    if detected and detected != courier_id
                    else ""
                )
                warn(
                    f"invalid {BY_ID[courier_id]['short']} format "
                    f"({BY_ID[courier_id]['desc']}).{hint}"
                )
                return 1
            return run_once(args, number, courier_id, client)

        return interactive(args, client)

    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
