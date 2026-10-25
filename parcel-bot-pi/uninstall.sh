#!/usr/bin/env bash
#
# Remove everything install.sh created.
#
#   sudo ./uninstall.sh           asks for confirmation, deletes the database
#   sudo ./uninstall.sh --yes     no prompt
#   sudo ./uninstall.sh --keep-data   keep /etc config and the SQLite database
#
# Your own virtualenv (~/python-env) is never touched.
#
set -euo pipefail

SERVICE_NAME=parcel-bot
APP_DIR=/opt/parcel-bot
CONF_DIR=/etc/parcel-bot
STATE_DIR=/var/lib/parcel-bot
SERVICE_FILE=/etc/systemd/system/parcel-bot.service
DROPIN_DIR=/etc/systemd/system/parcel-bot.service.d
DEDICATED_USER=parcelbot

ASSUME_YES=0
KEEP_DATA=0
for arg in "$@"; do
    case "$arg" in
        -y|--yes)       ASSUME_YES=1 ;;
        --keep-data)    KEEP_DATA=1 ;;
        -h|--help)      sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)              echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    echo "Run as root:  sudo ./uninstall.sh" >&2
    exit 1
fi

if [[ "$ASSUME_YES" -eq 0 ]]; then
    echo "This will remove:"
    echo "  service : $SERVICE_NAME"
    echo "  code    : $APP_DIR"
    [[ "$KEEP_DATA" -eq 1 ]] && echo "  config  : kept" || echo "  config  : $CONF_DIR"
    [[ "$KEEP_DATA" -eq 1 ]] && echo "  database: kept" || echo "  database: $STATE_DIR (users, reminders, quotas)"
    echo "  user    : $DEDICATED_USER (if it exists)"
    echo
    echo "Your personal virtualenv (e.g. ~/python-env) is NOT touched."
    echo
    read -r -p "Continue? [y/N] " reply
    case "$reply" in
        y|Y|yes|YES) ;;
        *) echo "Aborted."; exit 1 ;;
    esac
fi

echo "==> stopping and disabling the service"
systemctl disable --now "$SERVICE_NAME" >/dev/null 2>&1 || true
systemctl reset-failed "$SERVICE_NAME" >/dev/null 2>&1 || true

echo "==> removing the unit"
rm -f "$SERVICE_FILE"
rm -rf "$DROPIN_DIR"
systemctl daemon-reload

echo "==> removing files"
rm -rf "$APP_DIR"
if [[ "$KEEP_DATA" -eq 0 ]]; then
    rm -rf "$CONF_DIR" "$STATE_DIR"
fi

if id -u "$DEDICATED_USER" >/dev/null 2>&1; then
    echo "==> removing service user $DEDICATED_USER"
    userdel "$DEDICATED_USER" 2>/dev/null || true
fi

echo
echo "Removed."
if [[ "$KEEP_DATA" -eq 1 ]]; then
    echo "Kept: $CONF_DIR and $STATE_DIR"
fi
