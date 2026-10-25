#!/usr/bin/env bash
#
# Installer for the Parcel Tracker bot on Raspberry Pi OS / Debian.
#
# Two supported layouts:
#   * existing virtualenv  -> runs as YOU, using e.g. ~/python-env
#   * fresh virtualenv     -> runs as the dedicated "parcelbot" user in /opt
#
# Usage:
#   sudo ./install.sh                  auto-detect ~/python-env (falls back to a new venv)
#   sudo ./install.sh --new-venv       always create /opt/parcel-bot/.venv
#   sudo VENV_PATH=/path/to/venv ./install.sh
#   ./install.sh --check               show what would happen, change nothing
#
set -euo pipefail

APP_DIR=/opt/parcel-bot
CONF_DIR=/etc/parcel-bot
STATE_DIR=/var/lib/parcel-bot
SERVICE_FILE=/etc/systemd/system/parcel-bot.service
DROPIN_DIR=/etc/systemd/system/parcel-bot.service.d
SERVICE_NAME=parcel-bot
DEDICATED_USER=parcelbot
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CHECK=0
FORCE_NEW=0
UPDATE_ENV=0
REQUESTED_VENV="${VENV_PATH:-}"

usage() {
    cat <<'EOF'
Usage: sudo ./install.sh [options]

  --check, --dry-run   show what would be installed, change nothing
  --new-venv           ignore ~/python-env and create /opt/parcel-bot/.venv
  --update-env         overwrite /etc/parcel-bot/env from this folder's .env
  -h, --help           this help

Environment:
  VENV_PATH=/path/to/venv    use that virtualenv explicitly
EOF
}

for arg in "$@"; do
    case "$arg" in
        --check|--dry-run) CHECK=1 ;;
        --new-venv)        FORCE_NEW=1 ;;
        --update-env)      UPDATE_ENV=1 ;;
        -h|--help)         usage; exit 0 ;;
        *)                 echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

# Who invoked us (sudo keeps SUDO_USER; direct root has no one).
INVOKER="${SUDO_USER:-$(id -un)}"
INVOKER_HOME="$(getent passwd "$INVOKER" | cut -d: -f6 || true)"
[[ -n "$INVOKER_HOME" ]] || INVOKER_HOME="$HOME"

# Decide which virtualenv to use.
if [[ "$FORCE_NEW" -eq 1 ]]; then
    USE_EXTERNAL=0
elif [[ -n "$REQUESTED_VENV" ]]; then
    if [[ ! -x "$REQUESTED_VENV/bin/python" ]]; then
        echo "VENV_PATH=$REQUESTED_VENV does not contain bin/python" >&2
        exit 1
    fi
    USE_EXTERNAL=1
    CANDIDATE="$REQUESTED_VENV"
elif [[ -x "$INVOKER_HOME/python-env/bin/python" ]]; then
    USE_EXTERNAL=1
    CANDIDATE="$INVOKER_HOME/python-env"
else
    USE_EXTERNAL=0
fi

if [[ "$USE_EXTERNAL" -eq 1 ]]; then
    VENV_PATH="$CANDIDATE"
    RUN_USER="$INVOKER"
else
    VENV_PATH="$APP_DIR/.venv"
    RUN_USER="$DEDICATED_USER"
fi
RUN_GROUP="$(id -gn "$RUN_USER" 2>/dev/null || echo "$RUN_USER")"

# --------------------------------------------------------------------------- #
# --check: report and stop before touching anything
# --------------------------------------------------------------------------- #
if [[ "$CHECK" -eq 1 ]]; then
    echo "app dir     : $APP_DIR"
    echo "run as      : $RUN_USER:$RUN_GROUP"
    echo "virtualenv  : $VENV_PATH ($([[ "$USE_EXTERNAL" -eq 1 ]] && echo existing || echo 'to be created'))"
    if [[ -f "$CONF_DIR/env" ]]; then
        if grep -q "PASTE_BOT_TOKEN_HERE" "$CONF_DIR/env" 2>/dev/null; then
            echo "config      : $CONF_DIR/env (placeholder token)"
        elif grep -q "^TELEGRAM_BOT_TOKEN=..*" "$CONF_DIR/env" 2>/dev/null; then
            echo "config      : $CONF_DIR/env (token set)"
        else
            echo "config      : $CONF_DIR/env (token missing)"
        fi
    else
        echo "config      : $CONF_DIR/env (missing)"
    fi
    echo "database    : $STATE_DIR/parcel_bot.db"
    echo "service     : $SERVICE_NAME"
    if [[ "$USE_EXTERNAL" -eq 1 ]]; then
        echo "protecthome : read-only (venv lives under /home)"
    fi
    exit 0
fi

if [[ $EUID -ne 0 ]]; then
    echo "Run as root:  sudo ./install.sh" >&2
    echo "Preview first: ./install.sh --check" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found. Install it: sudo apt install -y python3 python3-venv" >&2
    exit 1
fi

echo "==> run user: $RUN_USER:$RUN_GROUP"
echo "==> virtualenv: $VENV_PATH ($([[ "$USE_EXTERNAL" -eq 1 ]] && echo existing || echo new))"

if [[ "$USE_EXTERNAL" -eq 0 ]]; then
    echo "==> creating service user"
    if ! id -u "$DEDICATED_USER" >/dev/null 2>&1; then
        useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$DEDICATED_USER"
    fi
fi

echo "==> creating directories"
install -d -o "$RUN_USER" -g "$RUN_GROUP" -m 0755 "$APP_DIR"
install -d -o root -g "$RUN_GROUP" -m 0750 "$CONF_DIR"
install -d -o "$RUN_USER" -g "$RUN_GROUP" -m 0750 "$STATE_DIR"

echo "==> copying application"
install -o "$RUN_USER" -g "$RUN_GROUP" -m 0644 \
    "$HERE/parcel_bot.py" "$HERE/track_parcel.py" "$HERE/requirements.txt" \
    "$APP_DIR/"
rm -rf "$APP_DIR/fixtures"
cp -r "$HERE/fixtures" "$APP_DIR/fixtures"
chown -R "$RUN_USER:$RUN_GROUP" "$APP_DIR"
install -o "$RUN_USER" -g "$RUN_GROUP" -m 0644 "$HERE/README.md" "$APP_DIR/README.md"

echo "==> preparing dependencies"
if [[ "$USE_EXTERNAL" -eq 1 ]]; then
    # never pip-install into a user venv as root
    sudo -u "$RUN_USER" "$VENV_PATH/bin/python" -m pip install --quiet --upgrade pip || true
    sudo -u "$RUN_USER" "$VENV_PATH/bin/python" -m pip install --quiet -r "$APP_DIR/requirements.txt"
else
    if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
        sudo -u "$RUN_USER" python3 -m venv "$APP_DIR/.venv"
    fi
    sudo -u "$RUN_USER" "$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
    sudo -u "$RUN_USER" "$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
fi

echo "==> installing configuration"
# Primary file: /etc/parcel-bot/env (dotenv syntax, read by the app and systemd).
ENV_SRC="$HERE/.env"
[[ -f "$ENV_SRC" ]] || ENV_SRC="$HERE/.env.example"

if [[ ! -f "$CONF_DIR/env" || "$UPDATE_ENV" -eq 1 ]]; then
    install -o root -g "$RUN_GROUP" -m 0640 "$ENV_SRC" "$CONF_DIR/env"
    [[ "$UPDATE_ENV" -eq 1 ]] && echo "    refreshed $CONF_DIR/env from $ENV_SRC"
fi

if grep -q "PASTE_BOT_TOKEN_HERE" "$CONF_DIR/env" 2>/dev/null; then
    NEEDS_EDIT=1
    echo "    ! token is still the placeholder"
elif ! grep -q "^TELEGRAM_BOT_TOKEN=..*" "$CONF_DIR/env" 2>/dev/null; then
    NEEDS_EDIT=1
    echo "    ! TELEGRAM_BOT_TOKEN is missing"
else
    NEEDS_EDIT=0
fi

echo "==> installing systemd unit"
install -m 0644 "$HERE/parcel-bot.service" "$SERVICE_FILE"

# When the venv lives outside /opt, point the unit at it via a drop-in.
rm -rf "$DROPIN_DIR"
if [[ "$USE_EXTERNAL" -eq 1 ]]; then
    install -d -m 0755 "$DROPIN_DIR"
    cat > "$DROPIN_DIR/override.conf" <<EOF
# generated by install.sh — external virtualenv
[Service]
User=$RUN_USER
Group=$RUN_GROUP
ExecStart=
ExecStart=$VENV_PATH/bin/python $APP_DIR/parcel_bot.py --run --config $CONF_DIR/config.ini --db $STATE_DIR/parcel_bot.db
ProtectHome=read-only
EOF
    chmod 0644 "$DROPIN_DIR/override.conf"
fi

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null

if [[ "$NEEDS_EDIT" -eq 1 ]]; then
    systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 || true
    cat <<EOF

Installed, but the bot is NOT started yet.

  1. edit the config (token + your chat id):
       sudo nano $CONF_DIR/env

  2. start it:
       sudo systemctl start $SERVICE_NAME

  3. follow the log:
       journalctl -u $SERVICE_NAME -f

EOF
else
    systemctl restart "$SERVICE_NAME"
    echo "Restarted $SERVICE_NAME."
fi

cat <<EOF

Useful commands:
  systemctl status $SERVICE_NAME
  systemctl restart $SERVICE_NAME
  systemctl disable $SERVICE_NAME
  journalctl -u $SERVICE_NAME -f

Uninstall:  sudo ./uninstall.sh

EOF
