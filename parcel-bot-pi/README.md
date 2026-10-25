# Parcel Tracker — Raspberry Pi deployment

Self-contained bundle for running the Telegram bot 24/7 on a Raspberry Pi.

```
parcel-bot-pi/
├── parcel_bot.py          the bot
├── track_parcel.py        tracking client (imported in live mode)
├── fixtures/              sample payloads for offline tests
├── requirements.txt       requests
├── .env                   the file you edit (token, webhook, admins, limits)
├── .env.example           template copied by the installer
├── config.ini.example     legacy INI alternative
├── parcel-bot.service     systemd unit
├── install.sh             installer (auto-detects ~/python-env)
├── uninstall.sh           removes the service, files and database
└── README.md              this file
```

After install:

| Path | Contents |
|---|---|
| `/opt/parcel-bot` | code + venv |
| `/etc/parcel-bot/config.ini` | secrets and settings |
| `/var/lib/parcel-bot/parcel_bot.db` | users, reminders, quotas |
| `/etc/systemd/system/parcel-bot.service` | the unit |

---

## 1. Copy the folder to the Pi

From your computer:

```bash
scp -r parcel-bot-pi pi@raspberrypi.local:~/
```

or copy it over Samba/USB. Nothing else is needed.

## 2. Install

```bash
ssh pi@raspberrypi.local
cd ~/parcel-bot-pi
chmod +x install.sh

./install.sh --check        # optional: show what it will do, changes nothing
sudo ./install.sh
```

The installer sets up `/opt/parcel-bot`, installs `requests`, copies the config
template, registers the systemd unit and enables it. It does **not** start the
bot until you have filled in the config.

### Virtualenv: existing or new

`install.sh` uses your existing `~/python-env` automatically when it exists:

```
$ ./install.sh --check
app dir     : /opt/parcel-bot
run as      : anirudh:anirudh
virtualenv  : /home/anirudh/python-env (existing)
protecthome : read-only (venv lives under /home)
```

In that mode:

* `requests` is installed **into your venv** as you (never as root);
* the service runs as **you**, not `parcelbot`;
* a systemd drop-in sets `ProtectHome=read-only` so the venv is reachable;
* no `parcelbot` user is created.

Options:

| Command | Venv used | Service runs as |
|---|---|---|
| `sudo ./install.sh` | `~/python-env` if present, else `/opt/parcel-bot/.venv` | you / `parcelbot` |
| `sudo ./install.sh --new-venv` | always `/opt/parcel-bot/.venv` | `parcelbot` |
| `sudo VENV_PATH=/srv/venv ./install.sh` | that path | you |

Your venv is never deleted by `uninstall.sh`.

## 3. Configure

### The one file you edit

Everything lives in a single dotenv file — **`/etc/parcel-bot/env`** on the Pi,
or **`.env`** next to the script when you run it manually. Never put secrets in
`parcel_bot.py`.

```bash
sudo nano /etc/parcel-bot/env
```

```sh
TELEGRAM_BOT_TOKEN=123456789:AAH8x...
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1234/abcd...
ADMIN_USER_IDS=123456789
FREE_TRACKS=2
WINDOW_HOURS=3
TRACKING_MODE=live
```

| Key | Required | Meaning |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | BotFather token |
| `DISCORD_WEBHOOK_URL` | no | used automatically for admin reminders |
| `ADMIN_USER_IDS` | for `/admin` | comma-separated numeric chat ids |
| `FREE_TRACKS` | no (default 2) | lookups per window for non-admins |
| `WINDOW_HOURS` | no (default 3) | window length |
| `TRACKING_MODE` | no (default `live` in this bundle) | `live` or `fixtures` |

> **Important:** editing `.env` inside this folder does **not** change an
> already-installed bot. The service runs from `/opt/parcel-bot` and reads
> **`/etc/parcel-bot/env`**. Either edit that file directly, or push this
> folder's `.env` with:
>
> ```bash
> sudo ./install.sh --update-env
> ```

The installer creates this file from `.env` (or `.env.example`) and the systemd
unit reads it via `EnvironmentFile=`; the app also reads it directly, so the
same file works for `python3 parcel_bot.py --run`.

Precedence: **process environment → `.env`/`/etc/parcel-bot/env` → legacy
`config.ini` → defaults**.

`config.ini` is still supported if you prefer INI syntax — put it at
`/etc/parcel-bot/config.ini` and pass `--config`. The dotenv file is simpler and
is what the installer sets up.

Apply changes with:

```bash
sudo chmod 640 /etc/parcel-bot/env
sudo systemctl restart parcel-bot
journalctl -u parcel-bot -n 20
```

### Editing before install (optional)

You can fill in `parcel-bot-pi/.env` on your computer before copying the folder;
the installer will use it as-is. Otherwise edit `/etc/parcel-bot/env` after
installing.

```ini
[telegram]
token = 123456789:AAH8x...

[discord]
webhook_url = https://discord.com/api/webhooks/1234/abcd...

[admin]
user_ids = 123456789

[limits]
free_tracks = 2
window_hours = 3

[tracking]
mode = live
```

* `token` — from [@BotFather](https://t.me/BotFather).
* `user_ids` — your numeric chat id. If you don't know it yet, leave it blank,
  start the bot, send `/start`, then read the log (see §7).
* `webhook_url` — optional. Used automatically for admin-created reminders.
* `mode = live` — real tracking. Set `fixtures` only for offline testing.

The file is installed `0640 root:parcelbot`; keep it that way.

## 4. Start

```bash
sudo systemctl start parcel-bot
sudo systemctl status parcel-bot
journalctl -u parcel-bot -f
```

First successful start looks like:

```
mode: LIVE                    pacing=5s             db=/var/lib/parcel-bot/parcel_bot.db
admin ids: 123456789
bot menu: /start  /reminders  /help  /admin
polling for updates…
```

It is already `enable`d, so it comes back automatically after reboot.

## 5. Day-to-day systemd

```bash
sudo systemctl status parcel-bot       # is it running?
sudo systemctl restart parcel-bot      # after a config or code change
sudo systemctl stop parcel-bot
sudo systemctl start parcel-bot
sudo systemctl disable parcel-bot      # don't start at boot
sudo systemctl enable parcel-bot       # start at boot (default after install)

journalctl -u parcel-bot -f            # live log
journalctl -u parcel-bot -n 100        # last 100 lines
journalctl -u parcel-bot --since today
```

Check it is enabled for boot:

```bash
systemctl is-enabled parcel-bot        # -> enabled
systemctl is-active parcel-bot         # -> active
```

## 6. Verify before going live

The bot can be exercised without hitting the tracking site:

```bash
cd /opt/parcel-bot
sudo -u parcelbot .venv/bin/python parcel_bot.py --simulate
sudo -u parcelbot .venv/bin/python parcel_bot.py \
     --config /etc/parcel-bot/config.ini \
     --test-notify EL836643777IN --dry-run
```

`--dry-run` prints the Telegram message and Discord JSON without sending either.
Drop `--dry-run` to send them for real (still no tracking request).

## 7. Finding your chat id

Start the bot and send `/start` in Telegram. The log prints:

```
! new user 123456789 · @yourhandle
```

Put `123456789` into `[admin] user_ids` and restart:

```bash
sudo nano /etc/parcel-bot/config.ini
sudo systemctl restart parcel-bot
```

The startup banner should now show `admin ids: 123456789`. Send `/admin`.

## 8. Updating the bot later

```bash
# from your computer, re-copy the changed files
scp parcel_bot.py track_parcel.py pi@raspberrypi.local:/tmp/
ssh pi@raspberrypi.local '
  sudo install -o parcelbot -g parcelbot -m 644 /tmp/parcel_bot.py /tmp/track_parcel.py /opt/parcel-bot/ &&
  sudo systemctl restart parcel-bot
'
```

Or re-run `sudo ./install.sh` from a fresh copy — it keeps `/etc` and the
database intact.

If you changed `.env` in this folder and want it applied to an existing install:

```bash
sudo ./install.sh --update-env
sudo systemctl restart parcel-bot
```

`--update-env` overwrites `/etc/parcel-bot/env`; the normal install never
overwrites it.

## 9. Data and backups

Everything that matters is in two paths:

```bash
sudo cp /etc/parcel-bot/env ~/parcel-bot.env.backup
sudo systemctl stop parcel-bot
sudo cp /var/lib/parcel-bot/parcel_bot.db ~/parcel_bot.db.backup
sudo systemctl start parcel-bot
```

The DB holds users, reminders, quotas and webhooks. It is created `0600` by the
bot (plus `StateDirectoryMode=0750` from systemd).

### Who has used the bot

Telegram does not expose a user list, so the bot records everyone who messages
it in the `users` table. Inspect it from the shell:

```bash
sudo -u parcelbot /opt/parcel-bot/.venv/bin/python \
  /opt/parcel-bot/parcel_bot.py --users --db /var/lib/parcel-bot/parcel_bot.db
```

```
Users (2)  db=/var/lib/parcel-bot/parcel_bot.db

CHAT ID        USERNAME            NAME              STATUS      LOOKUPS  JOINED             LAST SEEN
1001234567     @demo_user          Demo              free              2  24 Oct 2026 12:19  24 Oct 2026 13:04
123456789      @owner              Owner             admin             9  24 Oct 2026 12:20  24 Oct 2026 13:10
```

The same list is available in Telegram via `/admin → Users`. Fields stored per
user: `chat_id`, `username`, `first_name`, `last_name`, `is_admin`, `exempt`,
`track_count`, `window_start`, `created_at`, `last_seen_at`.

## 10. Behaviour on the Pi

* **Live tracking** (`mode = live`): real lookups, 5 s spacing, cached 10 min.
* **Free tier**: 2 lookups per 3 hours for non-admins; the 3rd is refused with a
  countdown and makes no request.
* **Admins** (config `user_ids` or granted via `/admin`) have no limits.
* **Reminders** every 3 hours, Telegram + optional Discord.
* **Restarts** keep reminders and quotas (SQLite).
* `Restart=always` restarts the bot within 10 s if it crashes; systemd starts it
  at boot after the network is online.

## 11. Troubleshooting

| Symptom | Fix |
|---|---|
| `status` shows `activating (auto-restart)` | `journalctl -u parcel-bot -n 50` — usually a bad token or missing config |
| `409 Conflict` in the log | another instance is polling (maybe you ran `--run` manually). Stop it: `sudo systemctl stop parcel-bot`, kill the manual one, start again |
| No reply in Telegram | check `TELEGRAM_BOT_TOKEN`, and that the service is `active` |
| `No Telegram token` | no token found in `/etc/parcel-bot/env` or `config.ini` |
| `Telegram rejected the token: Not Found` | the token is still `PASTE_BOT_TOKEN_HERE`, has no `:`, or has a stray space — Telegram builds an invalid `/bot<token>/` URL. Copy it again from BotFather |
| `Telegram rejected the token: Unauthorized` | wrong/revoked token — regenerate with `/token` in BotFather |
| `auth_key`/`admin ids: not set` | `ADMIN_USER_IDS` is empty in `/etc/parcel-bot/env` |
| `/admin` says "for the bot owner" | `user_ids` doesn't contain your chat id, or you didn't restart |
| Permission denied on the DB | `sudo chown -R parcelbot:parcelbot /var/lib/parcel-bot` |
| Bot starts but no notifications | `/reminders` — mode `only out for delivery` stays silent by design |
| Pi clock wrong after boot | `sudo timedatectl set-ntp true` (TLS/Telegram need a correct clock) |

## 12. Uninstall / clean up a failed install

Interrupted the installer (Ctrl-C during venv creation)? Remove the partial
install with the bundled script:

```bash
cd ~/parcel-bot-pi
sudo ./uninstall.sh
```

It stops and disables the service, removes the unit **and any drop-in**, deletes
`/opt/parcel-bot`, `/etc/parcel-bot`, `/var/lib/parcel-bot` (database included)
and removes the `parcelbot` user if it was created. Your `~/python-env` is
**never touched**.

Options:

```bash
sudo ./uninstall.sh --keep-data   # keep /etc config + SQLite database
sudo ./uninstall.sh --yes         # no confirmation prompt
```

Equivalent manual commands:

```bash
sudo systemctl disable --now parcel-bot
sudo rm -f /etc/systemd/system/parcel-bot.service
sudo rm -rf /etc/systemd/system/parcel-bot.service.d
sudo systemctl daemon-reload
sudo rm -rf /opt/parcel-bot /etc/parcel-bot /var/lib/parcel-bot
sudo userdel parcelbot 2>/dev/null || true
```

Run `sudo ./install.sh` again afterwards.

## 13. Security notes

* `config.ini` holds the bot token and webhook — `0640 root:parcelbot`, never in
  git.
* The unit runs as the unprivileged `parcelbot` user with `ProtectSystem=strict`,
  `ProtectHome=true` and `NoNewPrivileges=true`.
* No inbound ports are opened; the bot only makes outbound HTTPS calls
  (long-polling, tracking, Discord).
* Admin rights are chat-id based, never username based.
* If you use your own venv under `/home`, the unit runs as that user with
  `ProtectHome=read-only` instead of `true`. That is the trade-off for reusing
  `~/python-env`; the bot itself still writes only to `/var/lib/parcel-bot`.
