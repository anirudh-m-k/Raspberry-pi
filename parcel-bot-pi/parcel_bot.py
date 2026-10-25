#!/usr/bin/env python3
"""
parcel_bot.py — personal Telegram parcel tracker (offline-first).

Tracks parcels through the same backend as `track_parcel.py`, renders the result
as a readable Telegram message, and can push change notifications to Discord.

Modes
-----
  fixtures (default)  reads saved JSON snapshots from ./fixtures — never the network
  live (--live)       uses track_parcel.lookup() with its 5 s pacing

Examples
--------
  python3 parcel_bot.py --simulate
  python3 parcel_bot.py --render EL836643777IN
  python3 parcel_bot.py --render FMPP4392861093 --all
  python3 parcel_bot.py --check-now
  TELEGRAM_BOT_TOKEN=... python3 parcel_bot.py --run
  TELEGRAM_BOT_TOKEN=... python3 parcel_bot.py --run --live

Only `requests` is required (plus the stdlib).
"""

from __future__ import annotations

import argparse
import configparser
import html
import json
import os
import re
import sqlite3
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from track_parcel import (
    BY_ID,
    auto_detect,
    classify,
    collapse,
    event_clock,
    event_day,
    fmt_date,
    fmt_datetime,
    money,
    parse_iso,
    pretty_article_type,
    show,
    sort_events,
    weight,
)

try:
    import requests
except ImportError:  # pragma: no cover
    sys.stderr.write("This bot needs `requests`:\n    pip install requests\n")
    raise SystemExit(1)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DEFAULT_FIXTURES = Path("fixtures")
DEFAULT_DB = Path("parcel_bot.db")
TELEGRAM_API = "https://api.telegram.org/bot{token}"

TRACK_COOLDOWN = 0                # 0 = no short-term gap; the quota below is the only limit
REMINDER_INTERVAL = 3 * 3600      # automatic check interval
SCHEDULER_TICK = 60
FETCH_SPACING = 5.0
MESSAGE_LIMIT = 3800
LINE_CLIP = 160

# Free tier for non-admin users: N lookups inside a rolling window.
FREE_TRACK_LIMIT = 2
FREE_WINDOW = 3 * 3600
USERS_PAGE = 5

COURIER_EMOJI = {
    "speedpost": "📮",
    "bluedart": "🚀",
    "delhivery": "🚚",
    "flipkart": "🛒",
    "dtdc": "📦",
}

MENU_KEYBOARD: List[List[Dict[str, str]]] = [
    [
        {"text": "📮 Speed Post", "callback_data": "c:speedpost"},
        {"text": "🚀 BlueDart", "callback_data": "c:bluedart"},
    ],
    [
        {"text": "🚚 Delhivery", "callback_data": "c:delhivery"},
        {"text": "🛒 Flipkart", "callback_data": "c:flipkart"},
    ],
    [{"text": "📦 DTDC", "callback_data": "c:dtdc"}],
]

STATUS = {
    "booked": ("📮", "Booked"),
    "in_transit": ("🚚", "In Transit"),
    "out_for_delivery": ("🛵", "Out for Delivery"),
    "delivered": ("✅", "Delivered"),
    "rto": ("↩️", "Returning to Sender"),
    "no_data": ("❔", "No Data Yet"),
}

DISCORD_COLORS = {
    "delivered": 0x2ECC71,
    "out_for_delivery": 0x3498DB,
    "in_transit": 0xF1C40F,
    "booked": 0x95A5A6,
    "rto": 0xE67E22,
    "no_data": 0x7F8C8D,
}

SEP = "━" * 20

CONFIG = configparser.ConfigParser()
DEFAULT_DISCORD_WEBHOOK = ""


def load_env_file(path: Any) -> bool:
    """Load a simple KEY=VALUE file into os.environ (existing vars win)."""
    candidate = Path(str(path)).expanduser()
    if not candidate.is_file():
        return False
    try:
        lines = candidate.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
    return True


def load_env_files(explicit: Optional[str] = None) -> None:
    """Explicit path first, then ./.env, then the systemd env file."""
    if explicit:
        load_env_file(explicit)
    load_env_file(Path.cwd() / ".env")
    load_env_file(Path(__file__).resolve().parent / ".env")
    load_env_file("/etc/parcel-bot/env")


def load_config(path: Optional[str]) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    if path:
        candidate = Path(path)
        if candidate.exists():
            parser.read(candidate, encoding="utf-8")
    return parser


def apply_config(parser: configparser.ConfigParser) -> None:
    """Apply [limits] and [discord] from config.ini; CLI/env still win."""
    global FREE_TRACK_LIMIT, FREE_WINDOW, DEFAULT_DISCORD_WEBHOOK, CONFIG
    CONFIG = parser
    try:
        FREE_TRACK_LIMIT = int(
            os.environ.get(
                "FREE_TRACKS",
                parser.getint("limits", "free_tracks", fallback=FREE_TRACK_LIMIT),
            )
        )
    except ValueError:
        pass
    try:
        hours = os.environ.get(
            "WINDOW_HOURS",
            parser.getfloat("limits", "window_hours", fallback=FREE_WINDOW / 3600),
        )
        FREE_WINDOW = int(float(hours) * 3600)
    except ValueError:
        pass
    DEFAULT_DISCORD_WEBHOOK = (
        os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        or parser.get("discord", "webhook_url", fallback="").strip()
    )


def telegram_token() -> str:
    return (
        os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        or CONFIG.get("telegram", "token", fallback="").strip()
    )

# Emoji are presentation sugar; the delivered text is plain.
NO_EMOJI = True

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2300-\u23FF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]+ ?"
)


def plain(text: Any) -> str:
    """Strip emoji and tidy the spacing they leave behind.

    Applied to everything that leaves the bot (messages, buttons, embeds), so
    the source strings can stay readable without leaking icons to the chat.
    """
    value = "" if text is None else str(text)
    if not NO_EMOJI:
        return value
    value = value.replace("🆕 ", "(new) ")
    value = _EMOJI_RE.sub("", value)
    lines = []
    for line in value.split("\n"):
        # collapse runs of spaces that were not indentation
        line = re.sub(r"(?<=\S) {2,}(?=\S)", " ", line)
        lines.append(line.rstrip())
    return "\n".join(lines)


def plain_payload(value: Any) -> Any:
    """Recursively clean strings inside a Discord payload."""
    if isinstance(value, str):
        return plain(value)
    if isinstance(value, list):
        return [plain_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: plain_payload(item) for key, item in value.items()}
    return value


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def esc(value: Any) -> str:
    """HTML-escape any dynamic value for parse_mode=HTML."""
    return html.escape("" if value is None else str(value), quote=False)


def dash(value: Any) -> str:
    return esc(show(value))


def clip(text: str, limit: int = LINE_CLIP) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def normalize(number: str) -> str:
    return re.sub(r"\s+", "", str(number)).upper()


def ts_str(epoch: Optional[float]) -> str:
    if not epoch:
        return "—"
    return datetime.fromtimestamp(float(epoch)).strftime("%d %b %Y %H:%M")


def wait_label(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h" if minutes == 0 else f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def ts_short(epoch: Optional[float]) -> str:
    if not epoch:
        return "—"
    return datetime.fromtimestamp(float(epoch)).strftime("%d %b %H:%M")


def short_day(event: Dict[str, Any]) -> str:
    parsed = parse_iso(event.get("date"))
    return parsed.strftime("%d %b") if parsed else "—"


def short_when(date_str: Any, clock: Any) -> str:
    parsed = parse_iso(str(date_str) if date_str else None)
    day = parsed.strftime("%d %b") if parsed else "—"
    return f"{day} {clock}" if clock else day


def status_display(state: Any, fallback: Any = None) -> Tuple[str, str]:
    key = str(state or "")
    if key in STATUS:
        return STATUS[key]
    label = show(fallback)
    return ("📦", "Update" if label == "—" else label)


def mask_webhook(url: str) -> str:
    try:
        parts = urlsplit(url)
        segments = [s for s in parts.path.split("/") if s]
        if segments:
            segments[-1] = "••••"
        return f"{parts.scheme}://{parts.netloc}/" + "/".join(segments)
    except Exception:
        return "https://discord.com/api/webhooks/••••"


def is_discord_webhook(url: str) -> bool:
    url = (url or "").strip()
    prefixes = (
        "https://discord.com/api/webhooks/",
        "https://discordapp.com/api/webhooks/",
    )
    if not url.startswith(prefixes):
        return False
    tail = url.split("/api/webhooks/", 1)[-1].strip("/")
    return len(tail.split("/")) >= 2 and " " not in tail


def split_message(text: str, limit: int = MESSAGE_LIMIT) -> List[str]:
    if len(text) <= limit:
        return [text]
    chunks: List[str] = []
    current: List[str] = []
    size = 0
    for line in text.split("\n"):
        if len(line) > limit:
            line = line[: limit - 1] + "…"
        if current and size + len(line) + 1 > limit:
            chunks.append("\n".join(current))
            current, size = [line], len(line)
        else:
            current.append(line)
            size += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


# --------------------------------------------------------------------------- #
# Clock
# --------------------------------------------------------------------------- #

class RealClock:
    def now(self) -> float:
        return time.time()


class FakeClock:
    def __init__(self, start: Optional[float] = None) -> None:
        self._t = time.time() if start is None else float(start)

    def now(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += float(seconds)


# --------------------------------------------------------------------------- #
# Store
# --------------------------------------------------------------------------- #

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id         INTEGER NOT NULL,
    courier         TEXT    NOT NULL,
    tracking        TEXT    NOT NULL,
    webhook         TEXT,
    notify_mode     TEXT    NOT NULL DEFAULT 'all',
    created_at      REAL    NOT NULL,
    last_check_at   REAL,
    next_check_at   REAL    NOT NULL,
    last_status     TEXT,
    last_state      TEXT,
    last_fingerprint TEXT,
    last_seen_keys  TEXT,
    error_notified_at REAL,
    UNIQUE(chat_id, courier, tracking)
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    chat_id      INTEGER PRIMARY KEY,
    username     TEXT,
    first_name   TEXT,
    last_name    TEXT,
    is_admin     INTEGER NOT NULL DEFAULT 0,
    exempt       INTEGER NOT NULL DEFAULT 0,
    track_count  INTEGER NOT NULL DEFAULT 0,
    window_start REAL,
    created_at   REAL NOT NULL,
    last_seen_at REAL NOT NULL
);
"""


class Store:
    def __init__(self, path: Any) -> None:
        self.path = str(path)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()
        if self.path != ":memory:":
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    # -- meta --------------------------------------------------------------- #
    def get_meta(self, key: str) -> Optional[str]:
        with self.lock:
            row = self.conn.execute(
                "SELECT value FROM meta WHERE key=?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: Any) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )
            self.conn.commit()

    def cooldown_remaining(self, chat_id: int, now: float) -> float:
        last = self.get_meta(f"cooldown:{chat_id}")
        if not last:
            return 0.0
        try:
            return max(0.0, float(last) + TRACK_COOLDOWN - now)
        except ValueError:
            return 0.0

    def mark_track(self, chat_id: int, now: float) -> None:
        self.set_meta(f"cooldown:{chat_id}", now)

    # -- subscriptions ------------------------------------------------------ #
    def add_sub(
        self,
        chat_id: int,
        courier: str,
        tracking: str,
        notify_mode: str,
        seed: Dict[str, Any],
        now: float,
        interval: int = REMINDER_INTERVAL,
    ) -> int:
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO subscriptions
                    (chat_id, courier, tracking, webhook, notify_mode, created_at,
                     next_check_at, last_status, last_state, last_fingerprint,
                     last_seen_keys)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(chat_id, courier, tracking) DO UPDATE SET
                    notify_mode      = excluded.notify_mode,
                    next_check_at    = excluded.next_check_at,
                    last_status      = excluded.last_status,
                    last_state       = excluded.last_state,
                    last_fingerprint = excluded.last_fingerprint,
                    last_seen_keys   = excluded.last_seen_keys
                """,
                (
                    chat_id,
                    courier,
                    tracking,
                    None,
                    notify_mode,
                    now,
                    now + interval,
                    seed.get("last_status"),
                    seed.get("last_state"),
                    seed.get("last_fingerprint"),
                    seed.get("last_seen_keys"),
                ),
            )
            self.conn.commit()
            row = self.conn.execute(
                "SELECT id FROM subscriptions WHERE chat_id=? AND courier=? AND tracking=?",
                (chat_id, courier, tracking),
            ).fetchone()
        return int(row["id"])

    def get_sub(self, sub_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM subscriptions WHERE id=?", (sub_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_subs(self, chat_id: int) -> List[Dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM subscriptions WHERE chat_id=? ORDER BY id", (chat_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def due_subs(self, now: float) -> List[Dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM subscriptions WHERE next_check_at<=? "
                "ORDER BY next_check_at",
                (now,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_sub(self, sub_id: int, **fields: Any) -> None:
        if not fields:
            return
        columns = ", ".join(f"{key}=?" for key in fields)
        values = list(fields.values()) + [sub_id]
        with self.lock:
            self.conn.execute(
                f"UPDATE subscriptions SET {columns} WHERE id=?", values
            )
            self.conn.commit()

    def delete_sub(self, sub_id: int) -> None:
        with self.lock:
            self.conn.execute("DELETE FROM subscriptions WHERE id=?", (sub_id,))
            self.conn.commit()

    def set_mode(self, sub_id: int, mode: str) -> None:
        self.update_sub(sub_id, notify_mode=mode)

    # -- users & quota ------------------------------------------------------ #
    def upsert_user(
        self,
        chat_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_admin: bool = False,
        now: float = 0.0,
    ) -> None:
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO users
                    (chat_id, username, first_name, last_name, is_admin,
                     created_at, last_seen_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    username     = COALESCE(excluded.username, users.username),
                    first_name   = COALESCE(excluded.first_name, users.first_name),
                    last_name    = COALESCE(excluded.last_name, users.last_name),
                    is_admin     = MAX(users.is_admin, excluded.is_admin),
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    chat_id,
                    username,
                    first_name,
                    last_name,
                    1 if is_admin else 0,
                    now,
                    now,
                ),
            )
            self.conn.commit()

    def get_user(self, chat_id: int) -> Optional[Dict[str, Any]]:
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM users WHERE chat_id=?", (chat_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_users(self, limit: int, offset: int) -> List[Dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM users ORDER BY last_seen_at DESC, chat_id "
                "LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_users(self) -> int:
        with self.lock:
            row = self.conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        return int(row["n"] if row else 0)

    def is_admin(self, chat_id: int) -> bool:
        user = self.get_user(chat_id)
        return bool(user and user.get("is_admin"))

    def set_admin(self, chat_id: int, flag: bool) -> bool:
        if not self.get_user(chat_id):
            return False
        with self.lock:
            self.conn.execute(
                "UPDATE users SET is_admin=?, exempt=0, track_count=0, window_start=NULL "
                "WHERE chat_id=?",
                (1 if flag else 0, chat_id),
            )
            self.conn.execute("DELETE FROM meta WHERE key=?", (f"cooldown:{chat_id}",))
            self.conn.commit()
        return True

    def set_exempt(self, chat_id: int, exempt: bool, now: float) -> bool:
        user = self.get_user(chat_id)
        if not user:
            return False
        with self.lock:
            self.conn.execute(
                "UPDATE users SET exempt=?, track_count=0, window_start=NULL "
                "WHERE chat_id=?",
                (1 if exempt else 0, chat_id),
            )
            self.conn.execute("DELETE FROM meta WHERE key=?", (f"cooldown:{chat_id}",))
            self.conn.commit()
        return True

    def quota_wait(self, chat_id: int, now: float) -> float:
        """Seconds to wait before the next free lookup (0 = allowed)."""
        user = self.get_user(chat_id)
        if not user or user.get("is_admin") or user.get("exempt"):
            return 0.0
        start = float(user.get("window_start") or 0.0)
        count = int(user.get("track_count") or 0)
        if not start or now - start >= FREE_WINDOW:
            return 0.0
        if count < FREE_TRACK_LIMIT:
            return 0.0
        return max(0.0, start + FREE_WINDOW - now)

    def bump_usage(self, chat_id: int, now: float) -> None:
        user = self.get_user(chat_id)
        if not user or user.get("is_admin") or user.get("exempt"):
            return
        start = float(user.get("window_start") or 0.0)
        count = int(user.get("track_count") or 0)
        if not start or now - start >= FREE_WINDOW:
            start, count = now, 0
        with self.lock:
            self.conn.execute(
                "UPDATE users SET track_count=?, window_start=? WHERE chat_id=?",
                (count + 1, start, chat_id),
            )
            self.conn.commit()


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #

class FixtureProvider:
    """Serves saved snapshots: <ID>.json, <ID>.2.json, <ID>.3.json …"""

    def __init__(self, root: Any) -> None:
        self.root = Path(root)
        self.calls: Dict[str, int] = {}

    def fetch(self, courier: str, tracking: str) -> Dict[str, Any]:
        call = self.calls.get(tracking, 0) + 1
        self.calls[tracking] = call

        path = self._snapshot(tracking, call)
        if path is None:
            raise FileNotFoundError(
                f"no fixture for {tracking} in {self.root}"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("trackingNumber") != tracking:
            raise ValueError(
                f"fixture {path.name} is for {payload.get('trackingNumber')!r}, "
                f"not {tracking!r}"
            )
        payload["_source"] = "fixture"
        return payload

    def _snapshot(self, tracking: str, call: int) -> Optional[Path]:
        base = self.root / f"{tracking}.json"
        if call > 1:
            exact = self.root / f"{tracking}.{call}.json"
            if exact.exists():
                return exact
            # fall back to the highest numbered snapshot available
            index = call
            while index > 1:
                index -= 1
                candidate = self.root / f"{tracking}.{index}.json"
                if candidate.exists():
                    return candidate
        return base if base.exists() else None


class LiveProvider:
    """Real tracking, opt-in via --live. Reuses track_parcel's pacing."""

    def __init__(self) -> None:
        from track_parcel import TrackClient, lookup

        self._lookup = lookup
        self._client = TrackClient()
        sys.stderr.write(
            "⚠️  LIVE mode: real tracking requests will be made "
            f"(pacing {FETCH_SPACING:g}s).\n"
        )

    def fetch(self, courier: str, tracking: str) -> Dict[str, Any]:
        payload, _cached, _ts = self._lookup(
            self._client,
            tracking,
            courier,
            use_cache=True,
            refresh=False,
            delay=FETCH_SPACING,
        )
        payload["_source"] = "live"
        return payload


# --------------------------------------------------------------------------- #
# Transports
# --------------------------------------------------------------------------- #

class TelegramError(Exception):
    def __init__(self, description: str, retry_after: Optional[float] = None) -> None:
        super().__init__(description)
        self.retry_after = retry_after


class TelegramTransport:
    def __init__(self, token: str) -> None:
        self.base = TELEGRAM_API.format(token=token)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "parcel-bot/1.0"})

    def _call(self, method: str, **params: Any) -> Any:
        response = self.session.post(
            f"{self.base}/{method}", json=params, timeout=60
        )
        try:
            data = response.json()
        except ValueError:
            raise TelegramError(f"HTTP {response.status_code}")
        if not data.get("ok"):
            extra = data.get("parameters") or {}
            raise TelegramError(
                data.get("description") or "telegram error",
                extra.get("retry_after"),
            )
        return data.get("result")

    def send(
        self,
        chat_id: int,
        text: str,
        keyboard: Optional[List[List[Dict[str, str]]]] = None,
        reply_keyboard: Optional[List[List[str]]] = None,
    ) -> Optional[int]:
        text = plain(text)
        if keyboard:
            keyboard = [
                [
                    {"text": plain(button["text"]).strip(), **{k: v for k, v in button.items() if k != "text"}}
                    for button in row
                ]
                for row in keyboard
            ]
        chunks = split_message(text)
        last_id: Optional[int] = None
        for index, chunk in enumerate(chunks):
            params: Dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            if index == len(chunks) - 1:
                if reply_keyboard:
                    params["reply_markup"] = {
                        "keyboard": [[{"text": label} for label in row] for row in reply_keyboard],
                        "resize_keyboard": True,
                        "is_persistent": True,
                    }
                elif keyboard:
                    params["reply_markup"] = {"inline_keyboard": keyboard}
            for attempt in (1, 2):
                try:
                    result = self._call("sendMessage", **params)
                    last_id = int(result["message_id"]) if result else last_id
                    break
                except TelegramError as exc:
                    if exc.retry_after and attempt == 1:
                        time.sleep(min(float(exc.retry_after), 10))
                        continue
                    raise
        return last_id

    def edit(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        keyboard: Optional[List[List[Dict[str, str]]]] = None,
    ) -> bool:
        """Replace an existing message in place. Falls back to a new message."""
        text = plain(text)
        chunks = split_message(text)
        params: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": chunks[0],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if keyboard:
            params["reply_markup"] = {"inline_keyboard": keyboard}
        try:
            self._call("editMessageText", **params)
        except TelegramError as exc:
            if "not modified" in str(exc).lower():
                return True
            # let the caller decide how to recover (avoids a duplicate send)
            return False
        for chunk in chunks[1:]:
            self.send(chat_id, chunk)
        return True

    def answer(self, callback_id: str, text: Optional[str] = None) -> None:
        try:
            self._call("answerCallbackQuery", callback_query_id=callback_id, text=text or "")
        except Exception:
            pass

    def get_me(self) -> Dict[str, Any]:
        """Validate the token and return the bot account."""
        return self._call("getMe") or {}

    def set_commands(self, commands: List[Tuple[str, str]]) -> bool:
        """Populate the Telegram hamburger menu (the persistent Start button)."""
        try:
            self._call(
                "setMyCommands",
                commands=[
                    {"command": name, "description": desc}
                    for name, desc in commands
                ],
            )
            return True
        except Exception:
            return False

    def get_updates(self, offset: Optional[int] = None, timeout: int = 25) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            params["offset"] = offset
        return self._call("getUpdates", **params) or []


class ConsoleTransport:
    """Offline double: prints a framed transcript and records messages."""

    def __init__(self, stream: Any = None) -> None:
        self.stream = stream or sys.stdout
        self.messages: List[Dict[str, Any]] = []
        self.toasts: List[str] = []
        self.sent_texts: List[str] = []
        self.edits: List[Dict[str, Any]] = []
        self._next_id = 1

    def send(
        self,
        chat_id: int,
        text: str,
        keyboard: Optional[List[List[Dict[str, str]]]] = None,
        reply_keyboard: Optional[List[List[str]]] = None,
    ) -> Optional[int]:
        text = plain(text)
        if keyboard:
            keyboard = [
                [
                    {"text": plain(button["text"]).strip(), **{k: v for k, v in button.items() if k != "text"}}
                    for button in row
                ]
                for row in keyboard
            ]
        message_id = self._next_id
        self._next_id += 1
        self.sent_texts.append(text)
        self.messages.append(
            {
                "id": message_id,
                "chat_id": chat_id,
                "text": text,
                "keyboard": keyboard or [],
                "reply_keyboard": reply_keyboard or [],
            }
        )
        print(f"┌─ TELEGRAM → {chat_id} " + "─" * 30, file=self.stream)
        for line in text.split("\n"):
            print(f"│ {line}", file=self.stream)
        if reply_keyboard:
            rows = [" ".join(f"[{label}]" for label in row) for row in reply_keyboard]
            print("└─ keyboard: " + " | ".join(rows), file=self.stream)
        elif keyboard:
            rows = [" ".join(f"[{b['text']}]" for b in row) for row in keyboard]
            print("└─ buttons: " + " | ".join(rows), file=self.stream)
        else:
            print("└" + "─" * 44, file=self.stream)
        print(file=self.stream)
        return message_id

    def edit(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        keyboard: Optional[List[List[Dict[str, str]]]] = None,
    ) -> bool:
        text = plain(text)
        for message in self.messages:
            if message.get("id") == message_id:
                message["text"] = text
                message["keyboard"] = keyboard or []
                break
        self.edits.append({"id": message_id, "text": text})
        print(f"┌─ TELEGRAM (edited msg {message_id}) → {chat_id} " + "─" * 16, file=self.stream)
        for line in text.split("\n"):
            print(f"│ {line}", file=self.stream)
        if keyboard:
            rows = [" ".join(f"[{b['text']}]" for b in row) for row in keyboard]
            print("└─ buttons: " + " | ".join(rows), file=self.stream)
        else:
            print("└" + "─" * 44, file=self.stream)
        print(file=self.stream)
        return True

    def answer(self, callback_id: str, text: Optional[str] = None) -> None:
        if text:
            self.toasts.append(text)
            print(f"  · toast: {text}", file=self.stream)


class DiscordGone(Exception):
    pass


class DiscordClient:
    def send(self, url: str, payload: Dict[str, Any]) -> bool:
        for attempt in (1, 2):
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code in (200, 204):
                return True
            if response.status_code == 429 and attempt == 1:
                try:
                    wait = float(response.json().get("retry_after", 1))
                except ValueError:
                    wait = 1.0
                time.sleep(min(wait, 5))
                continue
            if response.status_code == 404:
                raise DiscordGone()
            return False
        return False


class DryRunDiscord:
    """Offline double: prints the exact webhook payload."""

    def __init__(self, stream: Any = None) -> None:
        self.stream = stream or sys.stdout
        self.payloads: List[Dict[str, Any]] = []

    def send(self, url: str, payload: Dict[str, Any]) -> bool:
        self.payloads.append(payload)
        print("┌─ DISCORD webhook (dry run) " + "─" * 26, file=self.stream)
        print(f"│ url: {mask_webhook(url)}", file=self.stream)
        for line in json.dumps(payload, indent=2, ensure_ascii=False).split("\n"):
            print(f"│ {line}", file=self.stream)
        print("└" + "─" * 52, file=self.stream)
        print(file=self.stream)
        return True


# --------------------------------------------------------------------------- #
# Detection helpers
# --------------------------------------------------------------------------- #

def event_key(event: Dict[str, Any]) -> str:
    return "|".join(str(event.get(k, "")) for k in ("date", "time", "office", "event"))


def event_keys(payload: Dict[str, Any]) -> List[str]:
    data = payload.get("data") or {}
    return [event_key(e) for e in sort_events(list(data.get("tracking_details") or []))]


def fingerprint(payload: Dict[str, Any]) -> str:
    data = payload.get("data") or {}
    return json.dumps(
        {"status": data.get("overall_status"), "keys": event_keys(payload)},
        sort_keys=True,
    )


def fresh_events(payload: Dict[str, Any], old_keys: List[str]) -> List[Dict[str, Any]]:
    seen = set(old_keys or [])
    data = payload.get("data") or {}
    events = sort_events(list(data.get("tracking_details") or []))
    return [e for e in events if event_key(e) not in seen]


def should_notify(sub: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    """notify_mode gates the alert, never the fetch."""
    data = payload.get("data") or {}
    new_state = str(data.get("overall_state") or "")
    if sub.get("notify_mode") == "out_for_delivery":
        prev_state = str(sub.get("last_state") or "")
        return prev_state != "out_for_delivery" and new_state == "out_for_delivery"
    return True


def seed_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload.get("data") or {}
    return {
        "last_status": data.get("overall_status"),
        "last_state": data.get("overall_state"),
        "last_fingerprint": fingerprint(payload),
        "last_seen_keys": json.dumps(event_keys(payload)),
    }


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def _route_parts(booking: Dict[str, Any], payload: Dict[str, Any]) -> Tuple[str, str, str, str]:
    origin = (
        booking.get("booked_at")
        or booking.get("origin_city")
        or booking.get("booking_office_name")
    )
    origin_pin = booking.get("origin_pincode") or booking.get("booking_pin")
    dest = (
        booking.get("delivery_location")
        or booking.get("destination_office_name")
        or booking.get("destination_city")
    )
    dest_pin = booking.get("destination_pincode")
    return (
        collapse(show(origin)),
        show(origin_pin),
        collapse(show(dest)),
        show(dest_pin),
    )


def clock_hm(event: Dict[str, Any]) -> str:
    """HH:MM only — journey lines do not need seconds."""
    text = event_clock(event)
    return text[:5] if len(text) >= 8 and text[2] == ":" else text


def stop_kind(event: Dict[str, Any]) -> str:
    """classify() maps "Out for delivery" to delivered (it contains 'deliver'),
    which is wrong for a journey marker."""
    status = str(event.get("status") or "").lower()
    label = str(event.get("event") or "").lower()
    if status == "out_for_delivery" or "out for delivery" in label:
        return "out_for_delivery"
    return classify(event)


def _stop_emoji(events: List[Dict[str, Any]], is_origin: bool = False) -> str:
    """Most recent meaningful state at a stop ("Item bagged" is not a state)."""
    mapping = {
        "booked": "📮",
        "dispatched": "🚚",
        "received": "📦",
        "out_for_delivery": "🛵",
        "delivered": "✅",
    }
    if is_origin and any(stop_kind(e) == "booked" for e in events):
        return "📮"
    for event in reversed(events):
        kind = stop_kind(event)
        if kind in mapping:
            return mapping[kind]
    return "•"


def journey_stops(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Group consecutive scans by office, oldest first.

    Same office may appear again later (a return trip); that is a new stop.
    Grouping is case-insensitive because couriers are inconsistent
    ("Farukhnagar" vs "FARUKHNAGAR").
    """
    data = payload.get("data") or {}
    events = sort_events(list(data.get("tracking_details") or []))
    stops: List[Dict[str, Any]] = []
    for event in events:
        office = collapse(show(event.get("office")))
        key = office.casefold()
        if stops and stops[-1]["key"] == key:
            stops[-1]["events"].append(event)
        else:
            stops.append({"office": office, "key": key, "events": [event]})
    return stops


def _scan_lines(events: List[Dict[str, Any]], new_keys: set) -> List[str]:
    """One bullet per scan: `• 22 Oct · 14:13 - Item Booked`."""
    shown = events[-4:]
    omitted = len(events) - len(shown)
    lines: List[str] = []
    if omitted:
        lines.append(f"   • +{omitted} earlier")
    for event in shown:
        label = clip(show(event.get("event")), 60)
        mark = " (new)" if event_key(event) in new_keys else ""
        lines.append(f"   • {short_day(event)} · {clock_hm(event)} - {label}{mark}")
    return lines


def render_journey(stops: List[Dict[str, Any]], new_keys: Optional[List[str]] = None) -> List[str]:
    """Telegram journey: place heading, one bullet per scan, ↓ between stops."""
    marked = set(new_keys or [])
    lines: List[str] = []
    for index, stop in enumerate(stops):
        emoji = _stop_emoji(stop["events"], is_origin=index == 0)
        lines.append(f"{emoji} <b>{esc(clip(stop['office'], 48))}</b>")
        lines.extend(_scan_lines(stop["events"], marked))
        if index < len(stops) - 1:
            lines.append(" ↓")
    return lines


def discord_journey(stops: List[Dict[str, Any]], new_keys: Optional[List[str]] = None) -> str:
    """Same layout, Markdown-bold headings, capped for a Discord embed field."""
    marked = set(new_keys or [])
    lines: List[str] = []
    for index, stop in enumerate(stops):
        emoji = _stop_emoji(stop["events"], is_origin=index == 0)
        lines.append(f"{emoji} **{stop['office']}**")
        lines.extend(_scan_lines(stop["events"], marked))
        if index < len(stops) - 1:
            lines.append("↓")
    text = "\n".join(lines)
    if len(text) > 1000:
        text = text[:1000].rsplit("\n", 1)[0] + "\n…"
    return text


def render_result(
    payload: Dict[str, Any],
    courier_id: str,
    now: float,
    source: str = "fixture",
) -> Tuple[str, List[List[Dict[str, str]]]]:
    cfg = BY_ID.get(courier_id, {})
    data = payload.get("data") or {}
    booking = data.get("booking_details") or {}
    events = sort_events(list(data.get("tracking_details") or []))
    state = str(data.get("overall_state") or "")
    emoji, label = status_display(state, data.get("overall_status"))
    number = payload.get("trackingNumber") or booking.get("article_number") or ""
    symbol = cfg.get("currency", "₹")

    lines: List[str] = []
    lines.append(f"📦 <b>{esc(cfg.get('name', courier_id))}</b>")
    lines.append(f"🆔 <code>{esc(number)}</code>")
    lines.append("")

    head = f"{emoji} <b>{esc(label)}</b>"
    if data.get("del_status"):
        head += f"  ·  {esc(data['del_status'])}"
    lines.append(head)

    if events:
        last = events[-1]
        lines.append(
            f"Last scan: {event_day(last)} {event_clock(last)} - "
            f"{esc(clip(show(last.get('event'))))} · "
            f"{esc(clip(collapse(show(last.get('office')))))}"
        )

    # -- route ------------------------------------------------------------- #
    from_place, from_pin, to_place, to_pin = _route_parts(booking, payload)
    lines.append("")
    lines.append(SEP)
    lines.append("🏁 <b>ROUTE</b>")
    lines.append(
        f"<b>From</b>  {esc(from_place)}"
        + (f" · {esc(from_pin)}" if from_pin != "—" else "")
    )
    booked_on = booking.get("booked_on") or booking.get("booking_date")
    if booked_on:
        lines.append(f"        booked {esc(fmt_datetime(booked_on))}")
    lines.append(
        f"<b>To</b>    {esc(to_place)}"
        + (f" · {esc(to_pin)}" if to_pin != "—" else "")
    )
    if booking.get("delivery_confirmed_on"):
        prefix = "returned" if state == "rto" else "delivered"
        lines.append(
            f"        {prefix} {esc(fmt_datetime(booking['delivery_confirmed_on']))}"
        )
    elif booking.get("expected_delivery_date"):
        lines.append(f"        ETA {esc(fmt_date(booking['expected_delivery_date']))}")
    else:
        lines.append("        ETA not published")

    # -- shipment ---------------------------------------------------------- #
    facts: List[Tuple[str, Optional[str]]] = [
        ("Type", pretty_article_type(booking.get("article_type"))),
        ("Booked", fmt_datetime(booked_on) if booked_on else None),
        (
            "Weight",
            weight(booking.get("weight_value"))
            if booking.get("weight_value") not in (None, "")
            else None,
        ),
        (
            "Tariff",
            money(booking.get("tariff"), symbol)
            if booking.get("tariff") not in (None, "")
            else None,
        ),
        (
            "COD",
            money(booking.get("cod_amount"), symbol)
            if booking.get("cod_amount") not in (None, "")
            else None,
        ),
    ]
    rows = [(k, v) for k, v in facts if v and v != "—"]
    if rows:
        lines.append("")
        lines.append("📋 <b>SHIPMENT</b>")
        for key, value in rows:
            lines.append(f"{key}: {esc(value)}")

    # -- journey ----------------------------------------------------------- #
    stops = journey_stops(payload)
    if stops:
        lines.append("")
        lines.append(
            f"🧭 <b>JOURNEY</b> <i>({len(stops)} stops · {len(events)} scans)</i>"
        )
        lines.append("")
        lines.extend(render_journey(stops))

    lines.append("")
    lines.append(f"<i>Fetched {ts_str(now)} · {esc(source)}</i>")

    keyboard = [
        [
            {"text": "🔔 Auto-update every 3h", "callback_data": f"rem:{courier_id}:{number}"},
            {"text": "🔄 Refresh", "callback_data": f"refresh:{courier_id}:{number}"},
        ],
        [
            {"text": "📋 All updates", "callback_data": f"all:{courier_id}:{number}"},
            {"text": "🏠 Menu", "callback_data": "menu"},
        ],
    ]
    return "\n".join(lines), keyboard


def render_empty(
    payload: Dict[str, Any], courier_id: str, now: float
) -> Tuple[str, List[List[Dict[str, str]]]]:
    cfg = BY_ID.get(courier_id, {})
    booking = (payload.get("data") or {}).get("booking_details") or {}
    number = payload.get("trackingNumber") or booking.get("article_number") or ""
    text = (
        "❔ <b>No scans yet</b>\n"
        f"🆔 <code>{esc(number)}</code> · {esc(cfg.get('short', courier_id))}\n\n"
        "The courier hasn't published any scan for this number.\n\n"
        "• Double-check the ID\n"
        "• Newly booked parcels can take up to 24 hours to appear"
    )
    keyboard = [
        [
            {"text": "🔄 Check again", "callback_data": f"refresh:{courier_id}:{number}"},
            {"text": "🏠 Menu", "callback_data": "menu"},
        ]
    ]
    return text, keyboard


def render_all(payload: Dict[str, Any], courier_id: str) -> str:
    cfg = BY_ID.get(courier_id, {})
    data = payload.get("data") or {}
    booking = data.get("booking_details") or {}
    events = sort_events(list(data.get("tracking_details") or []))
    number = payload.get("trackingNumber") or booking.get("article_number") or ""

    lines = [
        f"📋 <b>All updates</b> — <code>{esc(number)}</code>",
        f"<i>{esc(cfg.get('name', courier_id))} · {len(events)} scans · newest first</i>",
        "",
    ]
    for index, event in enumerate(reversed(events), start=1):
        lines.append(f"{index}. <b>{esc(show(event.get('event')))}</b>")
        lines.append(f"   {esc(collapse(show(event.get('office'))))}")
        detail = f"   {event_day(event)} {event_clock(event)}"
        if event.get("eventcode"):
            detail += f" · <code>{esc(event['eventcode'])}</code>"
        lines.append(detail)
        if event.get("remarks"):
            lines.append(f"   <i>{esc(clip(event['remarks']))}</i>")
        lines.append("")
    return "\n".join(lines).rstrip()


def _previous_summary(sub: Dict[str, Any], old_keys: List[str]) -> Optional[str]:
    if not old_keys:
        return None
    parts = (old_keys[-1].split("|") + ["", "", "", ""])[:4]
    date, clock, office, _event = parts
    status = sub.get("last_status") or ""
    when = short_when(date, clock)
    bits = [b for b in (status, office, when) if b]
    return " · ".join(bits) if bits else None


def render_delta(
    payload: Dict[str, Any],
    courier_id: str,
    fresh: List[Dict[str, Any]],
    previous: Optional[str],
    mode: str,
    sub_id: int,
) -> Tuple[str, List[List[Dict[str, str]]]]:
    cfg = BY_ID.get(courier_id, {})
    data = payload.get("data") or {}
    booking = data.get("booking_details") or {}
    number = payload.get("trackingNumber") or booking.get("article_number") or ""
    emoji, label = status_display(data.get("overall_state"), data.get("overall_status"))
    from_place, from_pin, to_place, to_pin = _route_parts(booking, payload)
    stops = journey_stops(payload)
    marked = [event_key(e) for e in fresh]

    route = f"{esc(from_place)} → {esc(to_place)}"
    if from_pin != "—" or to_pin != "—":
        route = (
            f"{esc(from_place)} ({esc(from_pin)}) → {esc(to_place)} ({esc(to_pin)})"
        )

    if mode == "out_for_delivery":
        latest = fresh[-1] if fresh else None
        headline = "🛵 <b>Out for delivery</b>"
        if latest:
            headline += (
                f" · {event_day(latest)} {clock_hm(latest)}"
            )
        lines = [
            headline,
            f"🆔 <code>{esc(number)}</code> · {esc(cfg.get('short', courier_id))}",
            "",
            "Your parcel is with the delivery agent today.",
        ]
    else:
        latest = fresh[-1] if fresh else None
        when = f" · {event_day(latest)} {clock_hm(latest)}" if latest else ""
        lines = [
            "🔔 <b>Parcel update</b>",
            f"🆔 <code>{esc(number)}</code> · {esc(cfg.get('short', courier_id))}",
            "",
            f"{emoji} <b>{esc(label)}</b>{when}",
        ]

    if stops:
        lines += [
            "",
            f"🧭 <b>JOURNEY</b> <i>({len(stops)} stops)</i>",
            "",
        ]
        lines.extend(render_journey(stops, marked))

    if from_place != "—" or to_place != "—":
        lines += ["", f"<b>Route</b> {route}"]
    if len(fresh) > 1:
        lines += ["", f"<i>(new) marks the {len(fresh)} scans added since the last check</i>"]
    elif fresh:
        lines += ["", "<i>(new) marks the scan added since the last check</i>"]

    if mode == "out_for_delivery":
        keyboard = [
            [
                {"text": "📋 All updates", "callback_data": f"all:{courier_id}:{number}"},
                {"text": "🔁 Switch to every update", "callback_data": f"tog:{sub_id}"},
                {"text": "🔕 Stop reminders", "callback_data": f"del:{sub_id}"},
            ]
        ]
    else:
        keyboard = [
            [
                {"text": "📋 All updates", "callback_data": f"all:{courier_id}:{number}"},
                {"text": "🔕 Stop reminders", "callback_data": f"del:{sub_id}"},
            ]
        ]
    return "\n".join(lines), keyboard


def render_list(subs: List[Dict[str, Any]]) -> Tuple[str, List[List[Dict[str, str]]]]:
    if not subs:
        return (
            "🔕 <b>No reminders yet.</b>\n\n"
            "Track a parcel and tap “🔔 Auto-update every 3h”.",
            [[{"text": "🏠 Menu", "callback_data": "menu"}]],
        )

    lines = [f"🔔 <b>Your reminders</b> ({len(subs)})", ""]
    buttons: List[List[Dict[str, str]]] = []
    for index, sub in enumerate(subs, start=1):
        cfg = BY_ID.get(sub["courier"], {})
        emoji, label = status_display(sub.get("last_state"), sub.get("last_status"))
        mode = (
            "📬 every update"
            if sub.get("notify_mode") == "all"
            else "🛵 only out for delivery"
        )
        lines.append(
            f"<b>{index}.</b> {emoji} <code>{esc(sub['tracking'])}</code> · "
            f"{esc(cfg.get('short', sub['courier']))}"
        )
        lines.append(
            f"   {esc(label)} · last checked {ts_short(sub.get('last_check_at'))}"
        )
        lines.append(f"   Notify: {mode}")
        lines.append(
            f"   Next: {ts_short(sub.get('next_check_at'))} · "
            f"Discord: {'on' if sub.get('webhook') else 'off'}"
        )
        lines.append("")
        target = "All" if sub.get("notify_mode") == "out_for_delivery" else "OFD"
        buttons.append(
            [
                {"text": f"Switch {index} → {target}", "callback_data": f"tog:{sub['id']}"},
                {"text": f"Delete {index}", "callback_data": f"del:{sub['id']}"},
            ]
        )
    buttons.append([{"text": "🏠 Menu", "callback_data": "menu"}])
    lines.append("Tap Switch to change the mode, Delete to stop a reminder.")
    return "\n".join(lines), buttons


def build_discord(
    payload: Dict[str, Any],
    courier_id: str,
    fresh: List[Dict[str, Any]],
    mode: str,
    now: float,
) -> Dict[str, Any]:
    cfg = BY_ID.get(courier_id, {})
    data = payload.get("data") or {}
    booking = data.get("booking_details") or {}
    state = str(data.get("overall_state") or "")
    _emoji, label = status_display(state, data.get("overall_status"))
    number = payload.get("trackingNumber") or booking.get("article_number") or ""
    from_place, from_pin, to_place, to_pin = _route_parts(booking, payload)
    stops = journey_stops(payload)
    marked = [event_key(e) for e in fresh]
    latest = fresh[-1] if fresh else None

    route = f"{from_place} → {to_place}"
    if from_pin != "—" or to_pin != "—":
        route = (
            f"{from_place} ({from_pin if from_pin != '—' else '?'}) → "
            f"{to_place} ({to_pin if to_pin != '—' else '?'})"
        )

    if latest:
        status_value = f"{label} · {event_day(latest)} {clock_hm(latest)}"
    else:
        status_value = label

    if mode == "out_for_delivery":
        title = f"Out for delivery · {number}"
        new_value = "Parcel is with the delivery agent today."
    else:
        title = f"{label} · {number}"
        names = [show(e.get("event")) for e in list(reversed(fresh))[:3]]
        if len(fresh) > 3:
            names.append(f"+{len(fresh) - 3} more")
        new_value = " · ".join(names) if names else "—"

    fields: List[Dict[str, Any]] = [
        {"name": "Courier", "value": cfg.get("name", courier_id), "inline": True},
        {"name": "Status", "value": clip(status_value, 120), "inline": True},
    ]
    if new_value:
        fields.append({"name": "New scans", "value": clip(new_value, 300), "inline": False})
    if stops:
        # A zero-width space keeps the blank line from being trimmed by Discord.
        journey_value = "\u200b\n" + discord_journey(stops, marked)
        fields.append(
            {
                "name": f"Journey · {len(stops)} stops",
                "value": journey_value,
                "inline": False,
            }
        )
    if route:
        fields.append({"name": "Route", "value": clip(route, 200), "inline": False})

    timestamp = (
        datetime.fromtimestamp(now, timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
    return plain_payload(
        {
            "username": "Parcel Tracker",
            "embeds": [
                {
                    "title": title,
                    "color": DISCORD_COLORS.get(state, 0x7F8C8D),
                    "fields": fields,
                    "footer": {"text": f"speedposttrack · {ts_str(now)}"},
                    "timestamp": timestamp,
                }
            ],
        }
    )


# --------------------------------------------------------------------------- #
# Bot
# --------------------------------------------------------------------------- #

class Bot:
    def __init__(
        self,
        transport: Any,
        provider: Any,
        store: Store,
        clock: Any = None,
        discord: Any = None,
        interval: int = REMINDER_INTERVAL,
        admin_ids: Optional[set] = None,
    ) -> None:
        self.transport = transport
        self.provider = provider
        self.store = store
        self.clock = clock or RealClock()
        self.discord = discord or DryRunDiscord()
        self.interval = int(interval)
        self.admin_ids = {int(x) for x in (admin_ids or set())}
        self.pending: Dict[int, Tuple[str, Any]] = {}
        self.results: Dict[Tuple[int, str, str], Dict[str, Any]] = {}
        self.last_discord_ok: Optional[bool] = None

    def log(self, message: str) -> None:
        print(f"  ! {message}", file=sys.stderr)

    def is_admin(self, chat_id: int) -> bool:
        chat_id = int(chat_id)
        return chat_id in self.admin_ids or self.store.is_admin(chat_id)

    def _remember(self, chat_id: Optional[int], sender: Dict[str, Any]) -> None:
        if chat_id is None:
            return
        known = self.store.get_user(int(chat_id))
        self.store.upsert_user(
            int(chat_id),
            username=sender.get("username"),
            first_name=sender.get("first_name"),
            last_name=sender.get("last_name"),
            is_admin=self.is_admin(int(chat_id)),
            now=self.clock.now(),
        )
        if known is None:
            handle = f"@{sender.get('username')}" if sender.get("username") else "no username"
            self.log(f"new user {chat_id} · {handle}")

    # -- dispatch ----------------------------------------------------------- #
    def handle_update(self, update: Dict[str, Any]) -> None:
        if "callback_query" in update:
            callback = update["callback_query"]
            chat_id = ((callback.get("message") or {}).get("chat") or {}).get("id")
            self._remember(chat_id, callback.get("from") or {})
            self._on_callback(callback)
            return
        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        self._remember(chat_id, message.get("from") or {})
        text = (message.get("text") or "").strip()
        if chat_id is None or not text:
            return
        if text.startswith("/"):
            self._on_command(chat_id, text.split()[0].lower())
            return
        self._on_text(chat_id, text)

    def _on_command(self, chat_id: int, command: str) -> None:
        if command in ("/start", "/menu"):
            self._greet(chat_id)
        elif command == "/reminders":
            self._send_list(chat_id)
        elif command == "/admin":
            self._admin_home(chat_id)
        elif command == "/cancel":
            self.pending.pop(chat_id, None)
            self.transport.send(chat_id, "👍 Cancelled.")
        elif command == "/skip":
            state = self.pending.get(chat_id)
            if state and state[0] == "webhook":
                self.pending.pop(chat_id, None)
                self.store.update_sub(int(state[1]), webhook=None)
                self.transport.send(chat_id, "👍 Telegram only. Send /reminders to manage it.")
            else:
                self.transport.send(chat_id, "Nothing to skip right now.")
        elif command == "/help":
            extra = (
                "\n/admin — owner panel (users, unlock a user)\n"
                if self.is_admin(chat_id)
                else ""
            )
            self.transport.send(
                chat_id,
                "🤖 <b>Parcel Tracker — help</b>\n\n"
                "/start — pick a courier\n"
                "/reminders — manage automatic updates\n"
                "/cancel — abort the current step\n"
                "/help — this message\n"
                f"{extra}\n"
                f"⚠️ Free accounts: {FREE_TRACK_LIMIT} lookups every "
                f"{FREE_WINDOW // 3600} hours.\n\n"
                "🔔 Reminders check every 3 hours and can be set to "
                "“every update” or “only out for delivery”.",
            )
        else:
            self.transport.send(chat_id, "Unknown command. Try /help.")

    def _on_text(self, chat_id: int, text: str) -> None:
        state = self.pending.get(chat_id)
        if not state:
            label = text.strip().lower()
            if label in ("start", "menu", "track a parcel"):
                self._greet(chat_id)
            elif label == "my reminders":
                self._send_list(chat_id)
            elif label == "help":
                self._on_command(chat_id, "/help")
            elif label == "admin":
                self._admin_home(chat_id)
            else:
                self.transport.send(
                    chat_id, "Pick a courier to get started 👇", MENU_KEYBOARD
                )
            return
        if state[0] == "id":
            self._track(chat_id, str(state[1]), normalize(text))
        elif state[0] == "webhook":
            self._capture_webhook(chat_id, int(state[1]), text.strip())
        elif state[0] == "admin_unlock":
            self._admin_unlock(chat_id, text.strip())
        elif state[0] == "admin_grant":
            self._admin_grant(chat_id, text.strip())

    # -- screens ------------------------------------------------------------ #
    def _reply_keyboard(self, chat_id: int) -> List[List[str]]:
        rows = [["Track a parcel"], ["My reminders", "Help"]]
        if self.is_admin(chat_id):
            rows.append(["Admin"])
        return rows

    def _greet(self, chat_id: int) -> None:
        limit_line = (
            "You have unlimited lookups."
            if self.is_admin(chat_id)
            else f"Free accounts get {FREE_TRACK_LIMIT} lookups every "
            f"{FREE_WINDOW // 3600} hours."
        )
        # Telegram allows only one reply_markup per message, so the welcome
        # installs the persistent keyboard and a second message carries the
        # inline courier buttons.
        self.transport.send(
            chat_id,
            "👋 <b>Parcel Tracker</b>\n\n"
            "I can follow India Post, BlueDart, Delhivery, Flipkart and DTDC parcels and\n"
            "ping you when something actually moves.\n\n"
            f"⚠️ <b>Heads up:</b> {limit_line}",
            reply_keyboard=self._reply_keyboard(chat_id),
        )
        self.transport.send(chat_id, "Pick a courier to begin 👇", MENU_KEYBOARD)

    def _ask_id(self, chat_id: int, courier: str) -> None:
        cfg = BY_ID.get(courier)
        if not cfg:
            self.transport.send(chat_id, "Unknown courier. /start to begin again.")
            return
        self.pending[chat_id] = ("id", courier)
        emoji = COURIER_EMOJI.get(courier, "📦")
        self.transport.send(
            chat_id,
            f"{emoji} <b>{esc(cfg['short'])}</b>\n\n"
            "Send me the tracking ID.\n\n"
            f"<b>Example:</b> <code>{esc(cfg['sample'])}</code>\n\n"
            "Tap Back to choose another courier.",
            [[{"text": "Back", "callback_data": "menu"}]],
        )

    def _deliver(
        self,
        chat_id: int,
        loading_id: Optional[int],
        text: str,
        keyboard: Optional[List[List[Dict[str, str]]]] = None,
    ) -> None:
        """Replace the 'Fetching…' message, or send fresh if there is none."""
        if loading_id is not None:
            try:
                if self.transport.edit(chat_id, loading_id, text, keyboard):
                    return
            except Exception as exc:  # noqa: BLE001
                self.log(f"could not edit the loading message: {exc}")
        self.transport.send(chat_id, text, keyboard)

    def _track(self, chat_id: int, courier: str, number: str) -> None:
        cfg = BY_ID.get(courier)
        if not cfg:
            self.transport.send(chat_id, "Unknown courier. /start to begin again.")
            return

        if not re.match(cfg["rx"], number):
            self.transport.send(
                chat_id,
                f"❌ That doesn't look like a {esc(cfg['short'])} ID.\n\n"
                f"Example: <code>{esc(cfg['sample'])}</code>\n\n"
                "Try again, or /cancel.",
            )
            return

        now = self.clock.now()
        admin = self.is_admin(chat_id)

        if not admin:
            if TRACK_COOLDOWN:
                remaining = self.store.cooldown_remaining(chat_id, now)
                if remaining > 0:
                    self.transport.send(
                        chat_id,
                        "⏳ <b>Slow down a little.</b>\n\n"
                        f"You can track the next ID in {wait_label(remaining)}.\n"
                        "This keeps the tracking service from blocking your IP.",
                    )
                    return

            quota = self.store.quota_wait(chat_id, now)
            if quota > 0:
                self.transport.send(
                    chat_id,
                    "🚦 <b>Tracking limit reached.</b>\n\n"
                    f"Free accounts can track {FREE_TRACK_LIMIT} parcels every "
                    f"{FREE_WINDOW // 3600} hours.\n"
                    f"Try again in {wait_label(quota)}.",
                )
                return

        loading_id = self.transport.send(
            chat_id, f"Fetching the details of {cfg['name']} package…"
        )

        try:
            payload = self.provider.fetch(courier, number)
        except FileNotFoundError:
            self._deliver(chat_id, loading_id, "⚠️ No sample data for this ID yet.")
            return
        except Exception as exc:  # noqa: BLE001 - never kill the poller
            self.log(f"fetch failed for {courier}/{number}: {exc}")
            self._deliver(
                chat_id,
                loading_id,
                "⚠️ Couldn't reach the courier. Try again in a few minutes.",
            )
            return

        self.store.mark_track(chat_id, now)
        self.store.bump_usage(chat_id, now)
        self.pending.pop(chat_id, None)
        self.results[(chat_id, courier, number)] = payload

        if str((payload.get("data") or {}).get("overall_state")) == "no_data":
            text, keyboard = render_empty(payload, courier, self.clock.now())
        else:
            text, keyboard = render_result(
                payload,
                courier,
                self.clock.now(),
                payload.get("_source", "fixture"),
            )
        self._deliver(chat_id, loading_id, text, keyboard)

    # -- reminders ---------------------------------------------------------- #
    def _offer_reminder(self, chat_id: int, courier: str, tracking: str) -> None:
        self.transport.send(
            chat_id,
            "🔔 <b>Automatic updates</b>\n\n"
            f"I'll check <code>{esc(tracking)}</code> every <b>3 hours</b> and "
            "message you only when there's something worth telling.\n\n"
            "Enable it?",
            [
                [
                    {"text": "✅ Yes, every 3 hours", "callback_data": f"rem_yes:{courier}:{tracking}"},
                    {"text": "✖️ No", "callback_data": f"rem_no:{courier}:{tracking}"},
                ]
            ],
        )

    def _ask_mode(self, chat_id: int, courier: str, tracking: str) -> None:
        self.transport.send(
            chat_id,
            "🔔 <b>What should I notify you about?</b>\n\n"
            "<b>1 · Every status update</b>\n"
            "   Any new scan the courier publishes.\n\n"
            "<b>2 · Only Out for Delivery</b>\n"
            "   One ping when the parcel leaves for delivery.",
            [
                [{"text": "📬 Every update", "callback_data": f"mode:all:{courier}:{tracking}"}],
                [{"text": "🛵 Only Out for Delivery", "callback_data": f"mode:ofd:{courier}:{tracking}"}],
                [{"text": "✖️ Cancel", "callback_data": "cancel"}],
            ],
        )

    def _create_sub(self, chat_id: int, courier: str, tracking: str, mode: str) -> None:
        payload = self.results.get((chat_id, courier, tracking))
        seed = seed_from_payload(payload) if payload else {}
        sub_id = self.store.add_sub(
            chat_id, courier, tracking, mode, seed, self.clock.now(),
            interval=self.interval,
        )
        label = "Every status update" if mode == "all" else "Only Out for Delivery"
        text = (
            f"✅ Reminder saved — <b>{label}</b>.\n\n"
            f"First check: {ts_str(self.clock.now() + self.interval)}\n"
        )
        if mode == "out_for_delivery":
            text += "I'll stay quiet until the parcel is out for delivery.\n"
        if self.is_admin(chat_id) and DEFAULT_DISCORD_WEBHOOK:
            self.store.update_sub(sub_id, webhook=DEFAULT_DISCORD_WEBHOOK)
            self.transport.send(
                chat_id,
                text
                + "\nChanged your mind? Send /reminders to switch modes or delete it."
                + "\n\nDiscord: using the webhook from config.ini.",
            )
            return

        text += (
            "\nChanged your mind? Send /reminders to switch modes or delete it.\n\n"
            "Want these updates mirrored to Discord as well?"
        )
        self.transport.send(
            chat_id,
            text,
            [
                [
                    {"text": "🎮 Add Discord webhook", "callback_data": f"wh_yes:{sub_id}"},
                    {"text": "💬 Telegram only", "callback_data": f"wh_no:{sub_id}"},
                ]
            ],
        )

    def _ask_webhook(self, chat_id: int, sub_id: int) -> None:
        self.pending[chat_id] = ("webhook", sub_id)
        self.transport.send(
            chat_id,
            "🎮 Send me your Discord webhook URL.\n\n"
            "Server Settings → Integrations → Webhooks → Copy Webhook URL\n"
            "It looks like:\n"
            "<code>https://discord.com/api/webhooks/…</code>\n\n"
            "/skip to keep Telegram only.",
            [[{"text": "✖️ Cancel", "callback_data": "cancel"}]],
        )

    def _capture_webhook(self, chat_id: int, sub_id: int, url: str) -> None:
        if url.lower() in ("/skip", "skip"):
            self.pending.pop(chat_id, None)
            self.store.update_sub(sub_id, webhook=None)
            self.transport.send(
                chat_id, "👍 Telegram only. Send /reminders to manage it."
            )
            return
        if not is_discord_webhook(url):
            self.transport.send(
                chat_id,
                "❌ That doesn't look like a Discord webhook URL.\n"
                "It should start with https://discord.com/api/webhooks/",
            )
            return
        self.pending.pop(chat_id, None)
        self.store.update_sub(sub_id, webhook=url)
        self.transport.send(
            chat_id,
            "✅ Discord webhook saved.\n\n"
            "I'll post there whenever this reminder fires.\n"
            "Send /reminders to manage it.",
        )

    def _send_list(self, chat_id: int) -> None:
        text, keyboard = render_list(self.store.list_subs(chat_id))
        self.transport.send(chat_id, text, keyboard)

    def _toggle_mode(self, chat_id: int, sub_id: int) -> str:
        sub = self.store.get_sub(sub_id)
        if not sub:
            self.transport.send(chat_id, "Reminder not found. /reminders to refresh.")
            return "Reminder not found."
        new_mode = "out_for_delivery" if sub["notify_mode"] == "all" else "all"
        self.store.set_mode(sub_id, new_mode)
        self._send_list(chat_id)
        return (
            "Now notifying: only out for delivery."
            if new_mode == "out_for_delivery"
            else "Now notifying: every update."
        )

    def _delete_sub(self, chat_id: int, sub_id: int) -> str:
        self.store.delete_sub(sub_id)
        self._send_list(chat_id)
        return "Reminder deleted."

    def _send_all(self, chat_id: int, courier: str, tracking: str) -> None:
        payload = self.results.get((chat_id, courier, tracking))
        if not payload:
            self.transport.send(
                chat_id, "Track this ID first, then open all updates."
            )
            return
        self.transport.send(chat_id, render_all(payload, courier))

    def _refresh(self, chat_id: int, courier: str, tracking: str) -> None:
        payload = self.results.get((chat_id, courier, tracking))
        if not payload:
            self._track(chat_id, courier, tracking)
            return
        text, keyboard = render_result(
            payload, courier, self.clock.now(), payload.get("_source", "fixture")
        )
        self.transport.send(chat_id, text, keyboard)

    # -- admin -------------------------------------------------------------- #
    def _admin_home(self, chat_id: int) -> None:
        if not self.is_admin(chat_id):
            self.transport.send(chat_id, "This command is for the bot owner.")
            return
        total = self.store.count_users()
        admins = ", ".join(str(x) for x in sorted(self.admin_ids)) or "not set"
        self.transport.send(
            chat_id,
            "<b>Admin panel</b>\n\n"
            f"Users: {total}\n"
            f"Free tier: {FREE_TRACK_LIMIT} lookups / {FREE_WINDOW // 3600}h\n"
            f"Admin ID(s): <code>{esc(admins)}</code>",
            [
                [{"text": "Users", "callback_data": "adm:users:0"}],
                [
                    {"text": "Unlock by ID", "callback_data": "adm:unlock"},
                    {"text": "Make admin", "callback_data": "adm:grant"},
                ],
            ],
        )

    def _admin_users(self, chat_id: int, page: int) -> None:
        if not self.is_admin(chat_id):
            return
        total = self.store.count_users()
        pages = max(1, (total + USERS_PAGE - 1) // USERS_PAGE)
        page = max(0, min(page, pages - 1))
        users = self.store.list_users(USERS_PAGE, page * USERS_PAGE)
        if not users:
            self.transport.send(chat_id, "<b>Users</b>\n\nNo users yet.")
            return

        lines = [
            f"<b>Users</b> ({total})  page {page + 1}/{pages}",
            "<i>Every row shows the username and the numeric ID.</i>",
            "",
        ]
        buttons: List[List[Dict[str, str]]] = []
        for index, user in enumerate(users, start=page * USERS_PAGE + 1):
            username = (
                f"@{user['username']}" if user.get("username") else "(no username)"
            )
            name = user.get("first_name") or "—"
            status = (
                "admin"
                if user.get("is_admin")
                else ("unlimited" if user.get("exempt") else "free")
            )
            used = int(user.get("track_count") or 0)
            lines.append(
                f"{index}. {esc(username)} · ID <code>{user['chat_id']}</code>"
            )
            lines.append(f"   {esc(name)} · {status} · {used} lookups this window")
            if int(user["chat_id"]) not in self.admin_ids:
                label = "Restrict" if user.get("exempt") else "Unlock"
                admin_label = "Remove admin" if user.get("is_admin") else "Make admin"
                buttons.append(
                    [
                        {
                            "text": f"{label} {user['chat_id']}",
                            "callback_data": f"adm:t:{user['chat_id']}",
                        },
                        {
                            "text": f"{admin_label} {user['chat_id']}",
                            "callback_data": f"adm:a:{user['chat_id']}",
                        },
                    ]
                )
        nav = []
        if page > 0:
            nav.append({"text": "Prev", "callback_data": f"adm:users:{page - 1}"})
        nav.append({"text": "Refresh", "callback_data": f"adm:users:{page}"})
        if page < pages - 1:
            nav.append({"text": "Next", "callback_data": f"adm:users:{page + 1}"})
        if nav:
            buttons.append(nav)
        buttons.append([{"text": "Back", "callback_data": "adm:home"}])
        self.transport.send(chat_id, "\n".join(lines), buttons)

    def _admin_prompt_unlock(self, chat_id: int) -> None:
        if not self.is_admin(chat_id):
            return
        self.pending[chat_id] = ("admin_unlock", None)
        self.transport.send(
            chat_id,
            "Send the USER ID (chat id) to unlock.\n\n"
            "Example: <code>123456789</code>\n"
            "/cancel to abort.",
        )

    def _admin_unlock(self, chat_id: int, text: str) -> None:
        if not self.is_admin(chat_id):
            return
        try:
            target = int(text)
        except ValueError:
            self.transport.send(chat_id, "That is not a numeric user ID. Try again or /cancel.")
            return
        user = self.store.get_user(target)
        if not user:
            self.transport.send(
                chat_id,
                f"No user with ID <code>{target}</code>. "
                "They need to message the bot once first.",
            )
            return
        self.pending.pop(chat_id, None)
        self.store.set_exempt(target, True, self.clock.now())
        if user.get("username"):
            handle = f"@{user['username']}"
        elif user.get("first_name"):
            handle = user["first_name"]
        else:
            handle = str(target)
        self.transport.send(
            chat_id,
            f"Unlocked <b>{esc(handle)}</b> (<code>{target}</code>).\n"
            "They now have unlimited lookups.",
        )

    def _admin_prompt_grant(self, chat_id: int) -> None:
        if not self.is_admin(chat_id):
            return
        self.pending[chat_id] = ("admin_grant", None)
        self.transport.send(
            chat_id,
            "Send the USER ID (chat id) to make an admin.\n\n"
            "Admins have no tracking limit and can open /admin.\n"
            "/cancel to abort.",
        )

    def _admin_grant(self, chat_id: int, text: str) -> None:
        if not self.is_admin(chat_id):
            return
        try:
            target = int(text)
        except ValueError:
            self.transport.send(chat_id, "That is not a numeric user ID. Try again or /cancel.")
            return
        if not self.store.get_user(target):
            self.transport.send(
                chat_id,
                f"No user with ID <code>{target}</code>. "
                "They need to message the bot once first.",
            )
            return
        self.pending.pop(chat_id, None)
        self.store.set_admin(target, True)
        user = self.store.get_user(target) or {}
        handle = f"@{user['username']}" if user.get("username") else str(target)
        self.transport.send(
            chat_id,
            f"<b>{esc(handle)}</b> (<code>{target}</code>) is now an admin.\n"
            "They have no tracking limit and can open /admin.",
        )

    def _admin_toggle_admin(self, chat_id: int, target: int) -> Optional[str]:
        if not self.is_admin(chat_id):
            return None
        if target in self.admin_ids:
            return "Owner ids cannot be changed."
        user = self.store.get_user(target)
        if not user:
            return "User not found."
        new_state = not bool(user.get("is_admin"))
        self.store.set_admin(target, new_state)
        self._admin_users(chat_id, 0)
        return "Admin access granted." if new_state else "Admin access removed."

    def _admin_toggle(self, chat_id: int, target: int) -> Optional[str]:
        if not self.is_admin(chat_id):
            return None
        user = self.store.get_user(target)
        if not user:
            return "User not found."
        new_state = not bool(user.get("exempt"))
        self.store.set_exempt(target, new_state, self.clock.now())
        self._admin_users(chat_id, 0)
        return "Unlocked." if new_state else "Restriction re-applied."

    # -- callbacks ---------------------------------------------------------- #
    def _on_callback(self, callback: Dict[str, Any]) -> None:
        callback_id = callback.get("id") or ""
        data = callback.get("data") or ""
        chat_id = ((callback.get("message") or {}).get("chat") or {}).get("id")
        if chat_id is None:
            return
        toast = None
        try:
            parts = data.split(":")
            head = parts[0] if parts else ""
            if head == "adm":
                action = parts[1] if len(parts) > 1 else "home"
                if action == "home":
                    self._admin_home(chat_id)
                elif action == "users":
                    self._admin_users(chat_id, int(parts[2]) if len(parts) > 2 else 0)
                elif action == "unlock":
                    self._admin_prompt_unlock(chat_id)
                elif action == "t" and len(parts) > 2:
                    toast = self._admin_toggle(chat_id, int(parts[2]))
                elif action == "a" and len(parts) > 2:
                    toast = self._admin_toggle_admin(chat_id, int(parts[2]))
                elif action == "grant":
                    self._admin_prompt_grant(chat_id)
            elif head == "menu":
                self.pending.pop(chat_id, None)
                self._greet(chat_id)
            elif head == "c" and len(parts) >= 2:
                self._ask_id(chat_id, parts[1])
            elif head == "cancel":
                self.pending.pop(chat_id, None)
                self.transport.send(chat_id, "👍 Cancelled.")
            elif head == "rem" and len(parts) >= 3:
                self._offer_reminder(chat_id, parts[1], parts[2])
            elif head == "rem_no":
                toast = None
            elif head == "rem_yes" and len(parts) >= 3:
                self._ask_mode(chat_id, parts[1], parts[2])
            elif head == "mode" and len(parts) >= 4:
                mode = "all" if parts[1] == "all" else "out_for_delivery"
                self._create_sub(chat_id, parts[2], parts[3], mode)
            elif head == "wh_yes" and len(parts) >= 2:
                self._ask_webhook(chat_id, int(parts[1]))
            elif head == "wh_no" and len(parts) >= 2:
                self.store.update_sub(int(parts[1]), webhook=None)
                toast = "Telegram only."
            elif head == "tog" and len(parts) >= 2:
                toast = self._toggle_mode(chat_id, int(parts[1]))
            elif head == "del" and len(parts) >= 2:
                toast = self._delete_sub(chat_id, int(parts[1]))
            elif head == "all" and len(parts) >= 3:
                self._send_all(chat_id, parts[1], parts[2])
            elif head == "refresh" and len(parts) >= 3:
                self._refresh(chat_id, parts[1], parts[2])
        except Exception as exc:  # noqa: BLE001 - never kill the poller
            self.log(f"callback {data!r} failed: {exc}")
            traceback.print_exc()
        finally:
            self.transport.answer(callback_id, toast)

    # -- scheduler ---------------------------------------------------------- #
    def check_subscription(self, sub: Dict[str, Any]) -> str:
        payload = self.provider.fetch(sub["courier"], sub["tracking"])
        data = payload.get("data") or {}
        now = self.clock.now()

        old_keys = json.loads(sub.get("last_seen_keys") or "[]")
        previous_fp = sub.get("last_fingerprint")
        current_fp = fingerprint(payload)
        baseline = previous_fp is None
        changed = (not baseline) and current_fp != previous_fp
        notify = changed and should_notify(sub, payload)
        new_events = fresh_events(payload, old_keys) if changed else []

        # Persist first: a crash or a failed send must never duplicate an alert.
        self.store.update_sub(
            sub["id"],
            last_check_at=now,
            next_check_at=now + self.interval,
            last_status=data.get("overall_status"),
            last_state=data.get("overall_state"),
            last_fingerprint=current_fp,
            last_seen_keys=json.dumps(event_keys(payload)),
        )

        if baseline:
            return "baseline"
        if not changed:
            return "unchanged"
        if not notify:
            return "suppressed"

        previous = _previous_summary(sub, old_keys)
        text, keyboard = render_delta(
            payload,
            sub["courier"],
            new_events,
            previous,
            str(sub.get("notify_mode") or "all"),
            int(sub["id"]),
        )
        self.results[(int(sub["chat_id"]), sub["courier"], sub["tracking"])] = payload
        self.transport.send(int(sub["chat_id"]), text, keyboard)

        if sub.get("webhook"):
            try:
                ok = self.discord.send(
                    sub["webhook"],
                    build_discord(
                        payload,
                        sub["courier"],
                        new_events,
                        str(sub.get("notify_mode") or "all"),
                        now,
                    ),
                )
                self.last_discord_ok = bool(ok)
                if not ok:
                    self.log("discord rejected the payload")
            except DiscordGone:
                self.last_discord_ok = False
                self.store.update_sub(int(sub["id"]), webhook=None)
                self.transport.send(
                    int(sub["chat_id"]),
                    "Discord webhook is gone — I removed it.",
                )
            except Exception as exc:  # noqa: BLE001
                self.last_discord_ok = False
                self.log(f"discord send failed: {exc}")

        return "notified"


class Scheduler:
    def __init__(self, bot: Bot, store: Store) -> None:
        self.bot = bot
        self.store = store
        self._thread: Optional[threading.Thread] = None

    @property
    def tick(self) -> float:
        return max(5.0, min(float(SCHEDULER_TICK), float(self.bot.interval)))

    def run_once(self) -> Dict[int, str]:
        results: Dict[int, str] = {}
        now = self.bot.clock.now()
        for sub in self.store.due_subs(now):
            try:
                results[int(sub["id"])] = self.bot.check_subscription(sub)
            except Exception as exc:  # noqa: BLE001
                self.bot.log(f"sweep failed for subscription {sub['id']}: {exc}")
                self.store.update_sub(int(sub["id"]), next_check_at=now + 1800)
        return results

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def loop() -> None:
            while True:
                try:
                    self.run_once()
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
                time.sleep(self.tick)

        self._thread = threading.Thread(target=loop, daemon=True, name="scheduler")
        self._thread.start()


# --------------------------------------------------------------------------- #
# Simulation (offline, fixture-driven)
# --------------------------------------------------------------------------- #

class Checker:
    def __init__(self) -> None:
        self.failures: List[str] = []
        self.passed = 0

    def check(self, condition: bool, label: str) -> None:
        if condition:
            self.passed += 1
            print(f"  ✔ {label}")
        else:
            self.failures.append(label)
            print(f"  ✘ {label}")

    def contains(self, haystack: str, needle: str, label: str) -> None:
        self.check(needle in haystack, f"{label} (found {needle!r})")


def _forbid_network():
    """Patch requests so any accidental network call fails loudly."""
    original = requests.sessions.Session.request

    def guard(self, method, url, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError(f"network call attempted in fixture mode: {url}")

    requests.sessions.Session.request = guard  # type: ignore[assignment]
    return original


def _stage(index: int, title: str) -> None:
    print(f"\n=== {index}. {title} " + "=" * max(0, 56 - len(title)))


def simulate(args: argparse.Namespace) -> int:
    store = Store(":memory:")
    provider = FixtureProvider(args.fixtures)
    transport = ConsoleTransport()
    discord = DryRunDiscord()
    clock = FakeClock(datetime(2026, 10, 23, 18, 46).timestamp())
    bot = Bot(transport, provider, store, clock, discord, admin_ids={2002})
    scheduler = Scheduler(bot, store)

    chat = 1001
    counter = {"n": 0}

    def send_text(text: str, as_chat: int = chat, username: str = "demo_user",
                  first_name: str = "Demo") -> None:
        bot.handle_update(
            {
                "message": {
                    "chat": {"id": as_chat},
                    "from": {
                        "id": as_chat,
                        "username": username,
                        "first_name": first_name,
                    },
                    "text": text,
                }
            }
        )

    def tap(data: str, as_chat: int = chat, username: str = "demo_user",
            first_name: str = "Demo") -> None:
        counter["n"] += 1
        bot.handle_update(
            {
                "callback_query": {
                    "id": f"cb{counter['n']}",
                    "data": data,
                    "from": {
                        "id": as_chat,
                        "username": username,
                        "first_name": first_name,
                    },
                    "message": {"chat": {"id": as_chat}},
                }
            }
        )

    def admin_text(text: str) -> None:
        send_text(text, as_chat=2002, username="owner", first_name="Owner")

    def admin_tap(data: str) -> None:
        tap(data, as_chat=2002, username="owner", first_name="Owner")

    def last_text() -> str:
        return transport.messages[-1]["text"] if transport.messages else ""

    def last_messages(count: int) -> List[str]:
        return [m["text"] for m in transport.messages[-count:]]

    original_request = _forbid_network()
    check = Checker()
    try:
        _stage(1, "/start")
        send_text("/start")
        check.check(
            transport.messages[-2]["reply_keyboard"]
            == [["Track a parcel"], ["My reminders", "Help"]],
            "start screen shows the persistent keyboard",
        )
        check.check(
            bool(transport.messages[-1]["keyboard"]),
            "start screen shows the inline courier buttons",
        )

        _stage(2, "tap Speed Post, then Back")
        tap("c:speedpost")
        back = transport.messages[-1]["keyboard"][0][0]
        check.check(
            back["text"] == "Back" and back["callback_data"] == "menu",
            "ID prompt offers a Back button",
        )
        tap("menu")
        check.check(
            "Pick a courier to begin" in last_text(),
            "Back returns to the courier menu",
        )
        tap("c:speedpost")

        _stage(3, "send EL836643777IN")
        send_text("EL836643777IN")
        result_text = last_text()
        check.contains(result_text, "India Post Speed Post", "courier name rendered")
        check.contains(result_text, "EL836643777IN", "tracking ID rendered")
        check.contains(result_text, "ROUTE", "route block rendered")
        check.contains(result_text, "Kulathur", "origin rendered")
        check.contains(result_text, "Adyar", "destination rendered")
        check.contains(result_text, "JOURNEY", "journey chain rendered")
        check.contains(result_text, "Item Dispatched", "dispatch status rendered")
        check.contains(result_text, "Item Received", "receive status rendered")
        check.contains(result_text, "Trivandrum Central", "intermediate stop rendered")
        check.contains(result_text, "Item bagged", "timeline rendered")
        check.check(
            any(
                text.startswith("Fetching the details of India Post Speed Post")
                for text in transport.sent_texts
            ),
            "a Fetching… placeholder is posted first",
        )
        check.check(
            any("India Post Speed Post" in edit["text"] for edit in transport.edits),
            "the placeholder is replaced by the result",
        )
        check.check(
            not any(ch in result_text for ch in "📮🚚📦✅🆕🔔🛵"),
            "rendered result contains no emoji",
        )

        _stage(4, "enable reminder → 📬 Every update")
        tap("rem:speedpost:EL836643777IN")
        tap("rem_yes:speedpost:EL836643777IN")
        tap("mode:all:speedpost:EL836643777IN")
        sub1 = store.list_subs(chat)[0]
        check.check(sub1["notify_mode"] == "all", "reminder #1 stored with mode=all")

        _stage(5, "add Discord webhook")
        tap(f"wh_yes:{sub1['id']}")
        send_text("https://discord.com/api/webhooks/123456789/abcdEFGH-token")
        sub1 = store.get_sub(sub1["id"])
        check.check(bool(sub1["webhook"]), "webhook stored")

        _stage(6, "second lookup (Flipkart) inside the free tier")
        tap("c:flipkart")
        send_text("FMPP4392861093")
        flipkart_text = last_text()
        check.contains(flipkart_text, "Flipkart", "flipkart result rendered")
        check.contains(flipkart_text, "TRIVANDRUM", "flipkart destination rendered")

        _stage(7, "third lookup hits the free limit")
        tap("c:speedpost")
        send_text("EL000000000IN")
        limit_text = last_text()
        check.contains(limit_text, "Tracking limit reached", "free limit enforced")
        check.contains(limit_text, "3 hours", "limit message states the 3-hour window")

        _stage(8, "admin lists users and unlocks the user")
        admin_text("/admin")
        check.contains(last_text(), "Admin panel", "admin panel opens for owner")
        admin_tap("adm:users:0")
        users_text = last_text()
        check.contains(users_text, "1001", "user list shows the chat id")
        check.contains(users_text, "@demo_user", "user list shows the username")
        check.contains(users_text, "ID <code>", "user list labels the ID column")
        admin_tap("adm:unlock")
        admin_text("1001")
        check.contains(last_text(), "Unlocked", "admin unlock confirmed")
        unlocked = store.get_user(chat)
        check.check(bool(unlocked and unlocked["exempt"]), "user marked exempt in SQLite")
        admin_tap(f"adm:a:{chat}")
        promoted = store.get_user(chat)
        check.check(bool(promoted and promoted["is_admin"]), "user promoted to admin in SQLite")
        admin_tap(f"adm:a:{chat}")
        demoted = store.get_user(chat)
        check.check(not bool(demoted and demoted["is_admin"]), "admin access removed again")

        _stage(9, "unlocked user can track again")
        tap("c:speedpost")
        send_text("EL000000000IN")
        check.contains(last_text(), "No scans yet", "lookup allowed after unlock")

        _stage(10, "enable reminder → 🛵 Only Out for Delivery")
        tap("rem:flipkart:FMPP4392861093")
        tap("rem_yes:flipkart:FMPP4392861093")
        tap("mode:ofd:flipkart:FMPP4392861093")
        subs = store.list_subs(chat)
        check.check(len(subs) == 2, "two reminders stored")
        sub2 = [s for s in subs if s["tracking"] == "FMPP4392861093"][0]
        check.check(sub2["notify_mode"] == "out_for_delivery", "reminder #2 stored with mode=out_for_delivery")
        tap(f"wh_yes:{sub2['id']}")
        send_text("https://discord.com/api/webhooks/987654321/zyxWVUTS-token")
        sub2 = store.get_sub(sub2["id"])
        check.check(bool(sub2["webhook"]), "webhook stored for reminder #2")

        _stage(11, "first sweep after 3h")
        clock.advance(3 * 3600)
        before = len(transport.messages)
        discord_before = len(discord.payloads)
        outcomes = scheduler.run_once()
        sent = [m["text"] for m in transport.messages[before:]]
        check.check(len(sent) == 2, f"two notifications sent (got {len(sent)})")
        joined = "\n".join(sent)
        check.contains(joined, "Item Delivered", "mode=all delta names the new scan")
        check.contains(joined, "JOURNEY", "mode=all delta shows the journey chain")
        check.contains(joined, "Kulathur", "mode=all delta starts at the origin")
        check.contains(joined, "Trivandrum Central", "mode=all delta keeps intermediate hubs")
        check.contains(joined, "Item Delivered (new)", "mode=all delta marks the new scan at the end")
        check.check(
            not any(ch in joined for ch in "📮🚚📦✅🆕🔔🛵"),
            "notifications contain no emoji",
        )
        check.contains(joined, "Out for delivery", "mode=out_for_delivery delta sent")
        check.check(len(discord.payloads) == discord_before + 2, "two Discord payloads built")
        check.check(all(p["embeds"][0]["title"] for p in discord.payloads), "Discord embeds have titles")
        check.check(
            any("EL836643777IN" in p["embeds"][0]["title"] for p in discord.payloads)
            and any("FMPP4392861093" in p["embeds"][0]["title"] for p in discord.payloads),
            "Discord titles carry both tracking IDs",
        )
        journey_fields = [
            field
            for payload in discord.payloads
            for field in payload["embeds"][0]["fields"]
            if field["name"].startswith("Journey")
        ]
        check.check(
            len(journey_fields) == 2
            and all(field["value"].startswith("\u200b\n") for field in journey_fields),
            "Discord journey fields start with a blank line",
        )

        _stage(12, "second sweep after 3h (nothing changed)")
        clock.advance(3 * 3600)
        before = len(transport.messages)
        scheduler.run_once()
        check.check(len(transport.messages) == before, "no messages on an unchanged sweep")

        _stage(13, "/reminders")
        send_text("/reminders")
        reminders_text = last_text()
        check.contains(reminders_text, "every update", "list shows mode=all")
        check.contains(reminders_text, "only out for delivery", "list shows mode=OFD")

        _stage(14, "toggle reminder #2")
        tap(f"tog:{sub2['id']}")
        sub2 = store.get_sub(sub2["id"])
        check.check(sub2["notify_mode"] == "all", "toggle flipped mode to all")

        _stage(15, "delete reminder #1")
        tap(f"del:{sub1['id']}")
        check.check(len(store.list_subs(chat)) == 1, "one reminder left after delete")
    finally:
        requests.sessions.Session.request = original_request  # type: ignore[assignment]

    # persistence check (separate file-backed store)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bot.db"
        first = Store(path)
        first.add_sub(chat, "speedpost", "EL836643777IN", "all", seed_from_payload(
            json.loads((Path(args.fixtures) / "EL836643777IN.json").read_text())
        ), clock.now())
        first.close()
        second = Store(path)
        persisted = second.list_subs(chat)
        second.close()
        check.check(len(persisted) == 1 and persisted[0]["notify_mode"] == "all",
                    "subscriptions survive a restart")

    # config.ini parsing (env would shadow the token, so clear it for the test)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        ini = Path(tmp) / "config.ini"
        ini.write_text(
            "[telegram]\ntoken = 123:ABC\n"
            "[discord]\nwebhook_url = https://discord.com/api/webhooks/1/tok\n"
            "[admin]\nuser_ids = 2002\n"
            "[limits]\nfree_tracks = 2\nwindow_hours = 3\n",
            encoding="utf-8",
        )
        keys = (
            "TELEGRAM_BOT_TOKEN",
            "ADMIN_USER_IDS",
            "DISCORD_WEBHOOK_URL",
            "FREE_TRACKS",
            "WINDOW_HOURS",
            "TRACKING_MODE",
        )
        saved = {key: os.environ.pop(key, None) for key in keys}
        try:
            apply_config(load_config(str(ini)))
            check.check(
                FREE_TRACK_LIMIT == 2 and FREE_WINDOW == 3 * 3600,
                "config limits loaded",
            )
            check.check(telegram_token() == "123:ABC", "config token loaded")
            check.check(admin_ids_from_env() == {2002}, "config admin ids loaded")
            check.check(
                DEFAULT_DISCORD_WEBHOOK.endswith("/1/tok"),
                "config Discord webhook loaded",
            )
        finally:
            for key, value in saved.items():
                if value is not None:
                    os.environ[key] = value

    print("\n" + "─" * 60)
    print(f"assertions passed: {check.passed}")
    if check.failures:
        print(f"assertions failed: {len(check.failures)}")
        for failure in check.failures:
            print(f"  ✘ {failure}")
        store.close()
        return 1

    print("✔ simulation complete — 0 network requests")
    store.close()
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def do_render(args: argparse.Namespace) -> int:
    number = normalize(args.tracking)
    courier = (args.courier or auto_detect(number) or "speedpost").lower()
    if courier not in BY_ID:
        sys.stderr.write(f"unknown courier: {courier}\n")
        return 1

    provider: Any = LiveProvider() if args.live else FixtureProvider(args.fixtures)
    try:
        payload = provider.fetch(courier, number)
    except FileNotFoundError:
        sys.stderr.write(f"no fixture for {number} in {args.fixtures}\n")
        return 1

    state = str((payload.get("data") or {}).get("overall_state") or "")
    if args.all:
        print(plain(render_all(payload, courier)))
    elif state == "no_data":
        print(plain(render_empty(payload, courier, time.time())[0]))
    else:
        print(
            plain(
                render_result(
                    payload, courier, time.time(), payload.get("_source", "fixture")
                )[0]
            )
        )
    return 0


def admin_ids_from_env() -> set:
    raw = (
        os.environ.get("ADMIN_USER_IDS")
        or os.environ.get("ADMIN_USER_ID")
        or CONFIG.get("admin", "user_ids", fallback="")
    )
    ids = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.add(int(part))
    return ids


def _discover_chat_id(transport: Any) -> Optional[int]:
    """Return the most recent chat that talked to the bot."""
    try:
        updates = transport.get_updates(timeout=0)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"could not fetch updates: {exc}\n")
        return None
    for update in reversed(updates or []):
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        if chat.get("id"):
            return int(chat["id"])
        callback = update.get("callback_query") or {}
        chat = (callback.get("message") or {}).get("chat") or {}
        if chat.get("id"):
            return int(chat["id"])
    return None


def do_test_notify(args: argparse.Namespace) -> int:
    """Send one real notification using fixture snapshots #1 and #2.

    Never contacts the tracking service: the payload comes from ./fixtures.
    """
    dry = bool(args.dry_run)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not dry and not token:
        sys.stderr.write(
            "TELEGRAM_BOT_TOKEN is not set.\n"
            "  export TELEGRAM_BOT_TOKEN=...\n"
            "  (or add --dry-run to preview without sending)\n"
        )
        return 1

    number = normalize(args.test_notify)
    courier = (args.courier or auto_detect(number) or "speedpost").lower()
    if courier not in BY_ID:
        sys.stderr.write(f"unknown courier: {courier}\n")
        return 1

    if dry:
        transport: Any = ConsoleTransport()
        chat_id = args.chat_id or 0
    else:
        transport = TelegramTransport(token)
        chat_id = args.chat_id or _discover_chat_id(transport)
        if not chat_id:
            sys.stderr.write(
                "No chat found for this bot yet.\n"
                "  1) open your bot in Telegram\n"
                "  2) send /start\n"
                "  3) run this command again (or pass --chat-id)\n"
            )
            return 1

    if args.webhook and not is_discord_webhook(args.webhook):
        sys.stderr.write(
            "That does not look like a Discord webhook URL.\n"
            "It should start with https://discord.com/api/webhooks/\n"
        )
        return 1

    print(f"source: {args.fixtures}/ (no tracking requests)")
    if dry:
        print("mode: DRY RUN (no Telegram send, no Discord post)")

    provider = FixtureProvider(args.fixtures)
    try:
        baseline = provider.fetch(courier, number)
    except FileNotFoundError:
        sys.stderr.write(f"no fixture for {number} in {args.fixtures}\n")
        return 1

    store = Store(":memory:")
    sub_id = store.add_sub(
        chat_id,
        courier,
        number,
        args.mode,
        seed_from_payload(baseline),
        time.time(),
        interval=args.interval,
    )
    if args.webhook and not dry:
        store.update_sub(sub_id, webhook=args.webhook)
        discord: Any = DiscordClient()
        real_webhook = True
    else:
        # dry run: keep a placeholder so the payload is still rendered
        store.update_sub(
            sub_id, webhook="https://discord.com/api/webhooks/dry-run/preview"
        )
        discord = DryRunDiscord()
        real_webhook = False

    bot = Bot(transport, provider, store, RealClock(), discord, interval=args.interval)

    print(f"→ chat {chat_id} · {courier}/{number} · mode={args.mode}")
    print(f"→ baseline: snapshot #1 ({len(baseline.get('data', {}).get('tracking_details') or [])} scans)")
    print("→ sending snapshot #2 as a change notification…")

    outcome = bot.check_subscription(store.get_sub(sub_id) or {})
    discord_ok = bot.last_discord_ok
    print(f"→ outcome: {outcome}")
    store.close()

    if outcome == "unchanged":
        sys.stderr.write(
            f"'{number}' has no second snapshot, so nothing changed.\n"
            f"Add fixtures/{number}.2.json or use EL836643777IN / FMPP4392861093.\n"
        )
        return 1
    if outcome != "notified":
        return 1

    if dry:
        print("dry run complete — nothing was sent")
        return 0

    print("✔ Telegram message sent")
    if not real_webhook:
        print("· Discord dry run shown above (pass --webhook to post for real)")
        return 0
    if discord_ok:
        print("✔ Discord webhook posted")
        return 0
    sys.stderr.write(
        "✘ Discord did not accept the payload.\n"
        "  Check the webhook URL is complete and the channel still exists.\n"
    )
    return 1


def do_list_users(args: argparse.Namespace) -> int:
    """Print every user the bot has seen (owner inspection, no Telegram needed)."""
    store = Store(args.db)
    try:
        total = store.count_users()
        users = store.list_users(1000, 0)
        if not users:
            print(f"no users yet in {args.db}")
            return 0
        print(f"Users ({total})  db={args.db}\n")
        header = (
            f"{'CHAT ID':<15}{'USERNAME':<20}{'NAME':<18}"
            f"{'STATUS':<11}{'LOOKUPS':>8}  {'JOINED':<18}LAST SEEN"
        )
        print(header)
        print("-" * len(header))
        for user in users:
            handle = f"@{user['username']}" if user.get("username") else "(none)"
            name = user.get("first_name") or ""
            status = (
                "admin"
                if user.get("is_admin")
                else ("unlimited" if user.get("exempt") else "free")
            )
            print(
                f"{user['chat_id']:<15}{clip(handle, 18):<20}{clip(name, 16):<18}"
                f"{status:<11}{int(user.get('track_count') or 0):>8}  "
                f"{ts_str(user.get('created_at')):<19}{ts_str(user.get('last_seen_at'))}"
            )
    finally:
        store.close()
    return 0


def _print_config_sources(args: argparse.Namespace) -> None:
    candidates = []
    if getattr(args, "env_file", None):
        candidates.append(args.env_file)
    candidates += [str(Path.cwd() / ".env"), "/etc/parcel-bot/env"]
    found = [path for path in candidates if path and Path(path).is_file()]
    if found:
        for path in dict.fromkeys(found):
            print(f"env : {path}")
    else:
        print("env : not found (./.env or /etc/parcel-bot/env)")

    ini = Path(args.config)
    print(f"ini : {args.config}" + ("" if ini.is_file() else " (not found)"))


def print_banner(args: argparse.Namespace) -> None:
    extra = (
        f"   interval={args.interval}s"
        if int(getattr(args, "interval", REMINDER_INTERVAL)) != REMINDER_INTERVAL
        else ""
    )
    if args.live:
        print(
            f"mode: LIVE                    pacing={FETCH_SPACING:g}s             db={args.db}{extra}"
        )
    else:
        print(
            f"mode: FIXTURES (no network)   fixtures={args.fixtures}   db={args.db}{extra}"
        )


def run_bot(args: argparse.Namespace) -> int:
    token = telegram_token()
    if not token:
        sys.stderr.write(
            "No Telegram token. Put it in config.ini ([telegram] token = ...)\n"
            "or export TELEGRAM_BOT_TOKEN.\n"
            "Offline demo: python3 parcel_bot.py --simulate\n"
        )
        return 1

    provider: Any = LiveProvider() if args.live else FixtureProvider(args.fixtures)
    store = Store(args.db)
    transport = TelegramTransport(token)
    discord = DiscordClient()
    admins = admin_ids_from_env()

    print_banner(args)
    _print_config_sources(args)

    try:
        me = transport.get_me()
    except TelegramError as exc:
        message = str(exc)
        sys.stdout.flush()
        print(f"  ! Telegram rejected the token: {message}", file=sys.stderr)
        print(
            "  ! Set TELEGRAM_BOT_TOKEN in /etc/parcel-bot/env "
            "(or [telegram] token in config.ini) and restart.",
            file=sys.stderr,
        )
        return 1
    print(f"bot: @{me.get('username', '?')} (id {me.get('id', '?')})")

    if admins:
        print(f"admin ids: {', '.join(str(x) for x in sorted(admins))}")
    else:
        print(
            "admin ids: not set — /admin disabled "
            "(add ADMIN_USER_IDS to /etc/parcel-bot/env)"
        )

    bot = Bot(
        transport,
        provider,
        store,
        RealClock(),
        discord,
        interval=args.interval,
        admin_ids=admins,
    )
    scheduler = Scheduler(bot, store)

    menu = [("start", "Track a parcel"), ("reminders", "My reminders"), ("help", "Help")]
    if admins:
        menu.append(("admin", "Owner panel"))
    if transport.set_commands(menu):
        print("bot menu: " + "  ".join(f"/{name}" for name, _ in menu))
    scheduler.start()

    offset: Optional[int] = None
    print("polling for updates… (Ctrl-C to stop)")
    while True:
        try:
            updates = transport.get_updates(offset, timeout=25)
        except TelegramError as exc:
            if exc.retry_after:
                time.sleep(min(float(exc.retry_after), 30))
            elif "409" in str(exc) or "Conflict" in str(exc):
                print("  ! another poller is running; backing off 30s", file=sys.stderr)
                time.sleep(30)
            else:
                print(f"  ! telegram: {exc}", file=sys.stderr)
                time.sleep(5)
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"  ! polling error: {exc}", file=sys.stderr)
            time.sleep(5)
            continue

        for update in updates:
            offset = int(update.get("update_id", 0)) + 1
            try:
                bot.handle_update(update)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Personal Telegram parcel tracker (offline-first).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 parcel_bot.py --simulate\n"
            "  python3 parcel_bot.py --render EL836643777IN\n"
            "  python3 parcel_bot.py --render FMPP4392861093 --all\n"
            "  python3 parcel_bot.py --check-now\n"
            "  TELEGRAM_BOT_TOKEN=... python3 parcel_bot.py --run\n"
            "  TELEGRAM_BOT_TOKEN=... python3 parcel_bot.py --run --live\n"
        ),
    )
    parser.add_argument("--simulate", action="store_true", help="offline scripted demo")
    parser.add_argument("--run", action="store_true", help="start Telegram long-polling")
    parser.add_argument(
        "--live",
        action="store_true",
        default=None,
        help="allow real network tracking (overrides [tracking] mode)",
    )
    parser.add_argument("--config", default="config.ini", help="path to config.ini")
    parser.add_argument(
        "--env-file",
        metavar="PATH",
        help="dotenv file with TELEGRAM_BOT_TOKEN, DISCORD_WEBHOOK_URL, ...",
    )
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="snapshot directory")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite path")
    parser.add_argument("--render", dest="tracking", metavar="ID", help="render a fixture and exit")
    parser.add_argument("--courier", help="courier id for --render")
    parser.add_argument("--all", action="store_true", help="with --render, show the full timeline")
    parser.add_argument("--check-now", action="store_true", help="run one scheduler sweep and exit")
    parser.add_argument(
        "--users",
        action="store_true",
        help="list users stored in the database and exit",
    )
    parser.add_argument(
        "--test-notify",
        metavar="ID",
        help="send one real notification from fixtures #1 -> #2, then exit",
    )
    parser.add_argument("--chat-id", type=int, help="with --test-notify, target this chat")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="with --test-notify, print Telegram + Discord output without sending",
    )
    parser.add_argument("--webhook", help="with --test-notify, post to this Discord webhook")
    parser.add_argument(
        "--mode",
        choices=("all", "out_for_delivery"),
        default="all",
        help="with --test-notify, which notification template to exercise",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=REMINDER_INTERVAL,
        metavar="SECONDS",
        help=f"reminder interval (default {REMINDER_INTERVAL}; use 60 for testing)",
    )
    parser.add_argument("--verbose", action="store_true", help="debug logging to stderr")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    load_env_files(args.env_file)
    apply_config(load_config(args.config))

    if args.live is None:
        mode = os.environ.get(
            "TRACKING_MODE", CONFIG.get("tracking", "mode", fallback="")
        ).strip().lower()
        args.live = mode == "live"

    if args.users:
        return do_list_users(args)

    if args.simulate:
        return simulate(args)

    if args.tracking:
        return do_render(args)

    if args.test_notify:
        return do_test_notify(args)

    if args.check_now:
        provider: Any = LiveProvider() if args.live else FixtureProvider(args.fixtures)
        store = Store(args.db)
        bot = Bot(
            ConsoleTransport(),
            provider,
            store,
            RealClock(),
            DiscordClient() if args.live else DryRunDiscord(),
            interval=args.interval,
            admin_ids=admin_ids_from_env(),
        )
        print_banner(args)
        outcomes = Scheduler(bot, store).run_once()
        for sub_id, outcome in outcomes.items():
            print(f"  subscription {sub_id}: {outcome}")
        store.close()
        return 0

    if args.run:
        try:
            return run_bot(args)
        except KeyboardInterrupt:
            print()
            return 0

    print_banner(args)
    print(
        "\nNothing to do. Pick one:\n"
        "  --simulate            offline end-to-end demo\n"
        "  --render ID           print one rendered result\n"
        "  --check-now           run a single reminder sweep\n"
        "  --run                 start the Telegram bot (needs TELEGRAM_BOT_TOKEN)\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
