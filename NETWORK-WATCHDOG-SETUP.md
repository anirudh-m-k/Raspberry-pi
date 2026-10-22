# Raspberry Pi Network Watchdog — Systemd Setup Guide

> **Purpose:** Auto-reboot Pi after 5 min of verified internet outage, capped at 1 reboot per hour with full logging. Fixes WiFi drop that kills SSH and forces power-cycle.

- **Platform:** Raspberry Pi (WiFi), Raspberry Pi OS / Debian / Ubuntu
- **Target:** Actual internet (8.8.8.8 + 1.1.1.1), not just LAN
- **Check interval:** 10s, **Debounce:** 30 consecutive failures = 5 min, **Cooldown:** 3600s (1/hr max)
- **Service type:** `systemd` `Type=simple` with `Restart=always` — **yes, this is a systemd service** (not cron).

All commands below run **on the Pi** (`anirudh@100.65.87.52`, home `/home/anirudh`), not on your dev machine. Copy `network-check/` to the Pi via `scp`.

```bash
# From your dev machine (where this repo lives):
scp -r /home/anirudh/Documents/Anirudh/Raspberry-Pi/network-check anirudh@100.65.87.52:/home/anirudh/
# Result on Pi: /home/anirudh/network-check/network_watchdog.sh
```

---

## 1. Files Included (in `network-check/`)

```
network-check/                          # after scp, on Pi at /home/anirudh/network-check/
├── network_watchdog.sh        # Main watchdog script
└── network-watchdog.service   # systemd unit
```

On Pi after `scp`, files are at `/home/anirudh/network-check/`. If you `git clone` the repo on the Pi instead, they will be at `/home/anirudh/Raspberry-Pi/network-check/` — adjust `cp` paths accordingly (both variants shown below).

---

## 2. Create the Watchdog Script (if not already present)

On the Pi (`/home/anirudh`):

```bash
sudo mkdir -p /usr/local/bin
sudo mkdir -p /var/lib/network-watchdog
sudo mkdir -p /var/log

# Copy from scp location (recommended — matches pwd /home/anirudh):
sudo cp /home/anirudh/network-check/network_watchdog.sh /usr/local/bin/network_watchdog.sh
sudo chmod +x /usr/local/bin/network_watchdog.sh

# If you git-cloned the repo on the Pi instead:
# sudo cp /home/anirudh/Raspberry-Pi/network-check/network_watchdog.sh /usr/local/bin/network_watchdog.sh

# Or create directly:
sudo nano /usr/local/bin/network_watchdog.sh
# paste content from network-check/network_watchdog.sh, save, then:
sudo chmod +x /usr/local/bin/network_watchdog.sh
```

Script does:

- `flock -n /run/network-watchdog.lock` — prevents duplicate instances
- `ping -c1 -W3 8.8.8.8` OR `ping -c1 -W3 1.1.1.1` — either success = online; fallback `curl -m5 https://1.1.1.1` if ICMP blocked
- Counter: 30 consecutive failures (10s * 30 = 5 min) before action
- Cooldown: checks `/var/lib/network-watchdog/last_reboot` (epoch); if elapsed < 3600s, logs `COOLDOWN_SKIP` and skips reboot
- Soft recovery before reboot: `systemctl try-restart NetworkManager` then re-pings once (WiFi reconnect often fixes without full reboot)
- Logs to `/var/log/network-watchdog.log` and `journalctl` via `logger -t network-watchdog`
- Supports `DRY_RUN=1` env var — logs `WOULD_REBOOT` without rebooting

---

## 3. Create the systemd Service

```bash
# From scp location (pwd /home/anirudh on Pi):
sudo cp /home/anirudh/network-check/network-watchdog.service /etc/systemd/system/network-watchdog.service

# If git-cloned:
# sudo cp /home/anirudh/Raspberry-Pi/network-check/network-watchdog.service /etc/systemd/system/network-watchdog.service

# Or create directly:
sudo nano /etc/systemd/system/network-watchdog.service
```

Content (`/etc/systemd/system/network-watchdog.service`):

```ini
[Unit]
Description=Network Watchdog - Reboot on 5min internet loss (1/hr cooldown)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/network_watchdog.sh
Restart=always
RestartSec=10
User=root
Environment=DRY_RUN=0
# Lock file and state dir are handled by script
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

---

## 4. Disable WiFi Power Save (Recommended for Pi WiFi drops)

Pi WiFi driver often drops due to power save. Apply once:

```bash
# For NetworkManager (Pi OS Bookworm / Ubuntu):
sudo mkdir -p /etc/NetworkManager/conf.d
echo -e "[connection]\nwifi.powersave = 2" | sudo tee /etc/NetworkManager/conf.d/wifi-powersave-off.conf
sudo systemctl restart NetworkManager

# Alternative for older dhcpcd / wpa_supplicant:
# sudo iw dev wlan0 set power_save off
# Add to /etc/rc.local or create udev rule to persist across boots

# Optional: enable hardware watchdog as second layer (survives script crash)
echo "dtparam=watchdog=on" | sudo tee -a /boot/firmware/config.txt
sudo apt update && sudo apt install -y watchdog
sudo systemctl enable --now watchdog
```

Verify power save is off:

```bash
iw dev wlan0 get power_save
# expected: Power save: off
```

---

## 5. Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable network-watchdog.service
sudo systemctl start network-watchdog.service

# Verify
sudo systemctl status network-watchdog.service --no-pager
sudo systemctl is-enabled network-watchdog.service
```

Expected status: `active (running)` and `enabled`.

---

## 6. Verify Logging and Cooldown

```bash
# Follow live logs (two sources, both written):
tail -f /var/log/network-watchdog.log
sudo journalctl -u network-watchdog -f

# Check last reboot timestamp (cooldown state):
cat /var/lib/network-watchdog/last_reboot
# contains epoch seconds, e.g. 1728576000
# check elapsed:
echo $(( $(date +%s) - $(cat /var/lib/network-watchdog/last_reboot) ))

# Dry-run test (no actual reboot, 2-3 min):
sudo systemctl stop network-watchdog.service
sudo DRY_RUN=1 /usr/local/bin/network_watchdog.sh &
# In another terminal, block internet to simulate outage:
# sudo iptables -A OUTPUT -d 8.8.8.8 -j DROP
# sudo iptables -A OUTPUT -d 1.1.1.1 -j DROP
# Wait 5 min, check log for WOULD_REBOOT, then restore:
# sudo iptables -D OUTPUT -d 8.8.8.8 -j DROP
# sudo iptables -D OUTPUT -d 1.1.1.1 -j DROP
# kill %1; sudo systemctl start network-watchdog.service
```

Manual trigger test (if you want to force the 5-min path quickly for demo, edit script threshold to 3 for test, then revert).

---

## 7. Cooldown Behavior — 1 Reboot / Hour

- First 5-min outage → reboot, writes `date +%s` to `/var/lib/network-watchdog/last_reboot`, logs `REBOOT triggering`.
- Second 5-min outage within 60 min → logs `COOLDOWN_SKIP reboot suppressed, <remaining>s remaining (1/hr limit)` and **does NOT reboot**. Counter resets, will re-evaluate after 10s.
- After 60 min elapses, next 5-min outage will reboot again.

Check cooldown logs:

```bash
grep -E "REBOOT|COOLDOWN_SKIP" /var/log/network-watchdog.log
sudo journalctl -u network-watchdog | grep -E "REBOOT|COOLDOWN_SKIP"
```

---

## 8. Daily Operations

```bash
# Status
sudo systemctl status network-watchdog.service --no-pager
tail -n 50 /var/log/network-watchdog.log

# Stop / Start / Restart
sudo systemctl stop network-watchdog.service
sudo systemctl start network-watchdog.service
sudo systemctl restart network-watchdog.service

# Disable (if you need to pause watchdog)
sudo systemctl disable --now network-watchdog.service

# Uninstall completely
sudo systemctl disable --now network-watchdog.service
sudo rm /etc/systemd/system/network-watchdog.service
sudo rm /usr/local/bin/network_watchdog.sh
sudo systemctl daemon-reload
# keep logs/state or remove: sudo rm -rf /var/lib/network-watchdog /var/log/network-watchdog.log
```

---

## 9. Log Rotation (Optional but Recommended)

```bash
sudo nano /etc/logrotate.d/network-watchdog
```

Content:

```
/var/log/network-watchdog.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    create 644 root root
}
```

Test: `sudo logrotate -d /etc/logrotate.d/network-watchdog`

---

## 10. Troubleshooting

| Symptom | Check |
|---|---|
| Service not starting | `sudo journalctl -u network-watchdog -n 50 --no-pager`, `sudo bash -n /usr/local/bin/network_watchdog.sh` |
| Reboot loop still happening | `cat /var/lib/network-watchdog/last_reboot` — if file missing, cooldown not working; check permissions `ls -l /var/lib/network-watchdog/` |
| False reboots on DNS-only failure | Script uses IP pings, not DNS, so DNS failure won't trigger reboot — correct |
| WiFi still drops daily | Confirm `iw dev wlan0 get power_save` is `off`; check `dmesg \| grep brcmfmac` for driver errors |
| Script runs twice | Check `ps aux \| grep network_watchdog`; `flock` should prevent — if using cron + systemd together, remove cron entry |
| Want to test without reboot | `sudo systemctl stop network-watchdog; sudo DRY_RUN=1 /usr/local/bin/network_watchdog.sh` |

---

## 11. Quick Copy-Paste Install (All-in-One, on Pi at /home/anirudh)

```bash
# 1. From DEV machine — push files to Pi (home is /home/anirudh):
scp -r /home/anirudh/Documents/Anirudh/Raspberry-Pi/network-check anirudh@100.65.87.52:/home/anirudh/
# Verify on Pi:
ssh anirudh@100.65.87.52 "ls -lh /home/anirudh/network-check/"

# 2. On Pi (ssh anirudh@100.65.87.52) — install
sudo mkdir -p /var/lib/network-watchdog /var/log
sudo cp /home/anirudh/network-check/network_watchdog.sh /usr/local/bin/network_watchdog.sh
sudo chmod +x /usr/local/bin/network_watchdog.sh
sudo cp /home/anirudh/network-check/network-watchdog.service /etc/systemd/system/network-watchdog.service
sudo systemctl daemon-reload
sudo systemctl enable --now network-watchdog.service
sudo systemctl status network-watchdog.service --no-pager
echo "Watchdog installed. Logs: tail -f /var/log/network-watchdog.log"

# If you git-cloned instead, replace /home/anirudh/network-check with /home/anirudh/Raspberry-Pi/network-check
```

---

## 12. Security Notes

- Service runs as `root` (required for `systemctl reboot` and `NetworkManager` restart). No passwordless sudo needed when run via systemd.
- State file `/var/lib/network-watchdog/last_reboot` is root-only (`644`).
- No outbound data, no credentials.

---

*Generated: 2026-10-10 | Setup for Raspberry Pi WiFi watchdog, systemd service, 10s check, 5 min debounce, 1 reboot/hr cooldown.*
