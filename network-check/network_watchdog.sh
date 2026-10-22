#!/usr/bin/env bash
# Raspberry Pi Network Watchdog — WiFi, internet-targeted, 1 reboot/hr cooldown
# - Checks actual internet every 10s via ping (8.8.8.8 + 1.1.1.1) and fallback curl
# - 30 consecutive failures (5 min) triggers action
# - Cooldown: 1 reboot per 3600s rolling window — logs COOLDOWN_SKIP if suppressed
# - Soft recovery before hard reboot (NetworkManager / cloudflared)
# - Logs to /var/log/network-watchdog.log and journalctl (logger)
# - Single instance via flock
# Install: sudo cp to /usr/local/bin/network_watchdog.sh && chmod +x
# Run via systemd: network-watchdog.service

set -o pipefail

# --- Config ---
CHECK_INTERVAL=10          # seconds between checks
FAIL_THRESHOLD=30          # 30 * 10s = 300s = 5 min
COOLDOWN_SEC=3600          # 1 reboot per hour max
STATE_FILE="/var/lib/network-watchdog/last_reboot"
LOG_FILE="/var/log/network-watchdog.log"
LOCK_FILE="/run/network-watchdog.lock"
PING_TARGET1="8.8.8.8"
PING_TARGET2="1.1.1.1"
CURL_FALLBACK="https://1.1.1.1"
# Set DRY_RUN=1 to log WOULD_REBOOT without rebooting (for testing)
DRY_RUN="${DRY_RUN:-0}"

# Ensure dirs exist (when run as root via systemd)
mkdir -p "$(dirname "$STATE_FILE")" 2>/dev/null
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null
touch "$LOG_FILE" 2>/dev/null

log() {
    local level="$1"
    local msg="$2"
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    local line="[$ts] [$level] $msg"
    echo "$line" | tee -a "$LOG_FILE" 2>/dev/null
    logger -t network-watchdog "[$level] $msg" 2>/dev/null || true
}

is_online() {
    # Either ping target succeeding counts as online
    if ping -c1 -W3 "$PING_TARGET1" >/dev/null 2>&1; then
        return 0
    fi
    if ping -c1 -W3 "$PING_TARGET2" >/dev/null 2>&1; then
        return 0
    fi
    # Fallback if ICMP is filtered — try curl to IP (no DNS)
    if command -v curl >/dev/null 2>&1; then
        if curl -s --max-time 5 --head "$CURL_FALLBACK" >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

try_soft_recovery() {
    log "INFO" "Attempting soft recovery before reboot (NetworkManager / cloudflared)"
    # Try NetworkManager (Pi OS Bookworm, Ubuntu)
    if systemctl is-active --quiet NetworkManager 2>/dev/null; then
        systemctl try-restart NetworkManager 2>/dev/null && log "INFO" "NetworkManager try-restart issued"
    elif systemctl is-active --quiet wpa_supplicant 2>/dev/null; then
        systemctl try-restart wpa_supplicant 2>/dev/null && log "INFO" "wpa_supplicant try-restart issued"
    elif systemctl is-active --quiet dhcpcd 2>/dev/null; then
        systemctl try-restart dhcpcd 2>/dev/null && log "INFO" "dhcpcd try-restart issued"
    fi
    # Also bounce cloudflared tunnel — often dies while WiFi recovers
    if systemctl is-active --quiet cloudflared 2>/dev/null || systemctl is-enabled --quiet cloudflared 2>/dev/null; then
        systemctl try-restart cloudflared 2>/dev/null && log "INFO" "cloudflared try-restart issued"
    fi
    sleep 10
    if is_online; then
        log "INFO" "Soft recovery succeeded — online again, reboot cancelled"
        return 0
    else
        log "WARN" "Soft recovery did not restore internet — proceeding to reboot check"
        return 1
    fi
}

should_reboot() {
    local now last elapsed remaining
    now="$(date +%s)"
    last="0"
    if [[ -f "$STATE_FILE" ]]; then
        last="$(cat "$STATE_FILE" 2>/dev/null || echo 0)"
        # sanitize — must be numeric
        if ! [[ "$last" =~ ^[0-9]+$ ]]; then
            last="0"
        fi
    fi
    elapsed=$((now - last))
    if [[ "$elapsed" -lt "$COOLDOWN_SEC" ]]; then
        remaining=$((COOLDOWN_SEC - elapsed))
        log "COOLDOWN_SKIP" "reboot suppressed — $remaining s remaining (1/hr limit), last reboot $(date -d "@$last" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "@$last")"
        return 1
    fi
    return 0
}

do_reboot() {
    if [[ "$DRY_RUN" == "1" ]]; then
        log "WOULD_REBOOT" "DRY_RUN=1 — would have rebooted now (5 min down, cooldown passed)"
        date +%s > "$STATE_FILE" 2>/dev/null || true
        return 0
    fi
    log "REBOOT" "triggering systemctl reboot — 5 min internet down, cooldown passed"
    date +%s > "$STATE_FILE" 2>/dev/null || true
    # Give log a moment to flush
    sleep 2
    /usr/bin/systemctl reboot 2>/dev/null || /sbin/reboot 2>/dev/null || reboot 2>/dev/null
}

# --- Single instance via flock ---
exec 9>"$LOCK_FILE" 2>/dev/null || exec 9>/tmp/network-watchdog.lock
if ! flock -n 9 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] Another watchdog instance is running — exiting" | tee -a "$LOG_FILE" 2>/dev/null
    logger -t network-watchdog "[ERROR] Another instance running — exiting" 2>/dev/null || true
    exit 0
fi

log "INFO" "Network watchdog started — interval=${CHECK_INTERVAL}s, threshold=${FAIL_THRESHOLD} (5 min), cooldown=${COOLDOWN_SEC}s, DRY_RUN=${DRY_RUN}"

fail_count=0
while true; do
    if is_online; then
        if [[ "$fail_count" -gt 0 ]]; then
            log "RECOVERED" "internet recovered after $fail_count/$FAIL_THRESHOLD failures"
        fi
        fail_count=0
    else
        fail_count=$((fail_count + 1))
        log "OFFLINE" "$fail_count/$FAIL_THRESHOLD — internet unreachable (ping $PING_TARGET1/$PING_TARGET2 + curl failed)"

        if [[ "$fail_count" -ge "$FAIL_THRESHOLD" ]]; then
            log "WARN" "$FAIL_THRESHOLD consecutive failures reached — 5 min down"

            # Try soft recovery once before hard reboot
            if try_soft_recovery; then
                fail_count=0
            else
                if should_reboot; then
                    do_reboot
                    # If reboot didn't happen (dry-run), reset counter to avoid busy-loop
                    fail_count=0
                else
                    # Cooldown suppressed — reset counter, re-evaluate in next interval
                    fail_count=0
                fi
            fi
        fi
    fi
    sleep "$CHECK_INTERVAL"
done
