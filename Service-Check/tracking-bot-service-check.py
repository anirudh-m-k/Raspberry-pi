#!/usr/bin/env python3
"""
Parcel Tracker bot - systemd service check & control
================================================================================

Checks whether the tracking bot service is running and lets you start, stop or
restart it. Modelled on pnr-bot-service-check.py for a consistent experience on
the Pi.

USAGE
    python3 tracking-bot-service-check.py            # interactive menu
    python3 tracking-bot-service-check.py status     # one-shot, no prompt
    python3 tracking-bot-service-check.py start
    python3 tracking-bot-service-check.py stop
    python3 tracking-bot-service-check.py restart

SERVICE
    Default unit: parcel-bot  (installed by parcel-bot-pi/install.sh)

    If your unit has a different name, either edit SERVICE_NAME below or run:

        TRACKING_BOT_SERVICE=tracking-bot python3 tracking-bot-service-check.py

NOTES
    * start/stop/restart use sudo unless you are already root.
    * No third-party packages required - standard library only.
================================================================================
"""

import os
import subprocess
import sys
import time

# systemd unit name (without or with ".service", both are accepted by systemctl)
SERVICE_NAME = os.environ.get("TRACKING_BOT_SERVICE", "parcel-bot")


# --------------------------------------------------------------------------- #
# systemd helpers
# --------------------------------------------------------------------------- #

def systemd_available():
    """True when systemctl exists and a running systemd is PID 1."""
    if not os.path.isdir("/run/systemd/system"):
        return False
    try:
        subprocess.run(
            ["systemctl", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except Exception:
        return False


def unit_exists():
    """True when systemd knows this unit (installed or generated)."""
    try:
        result = subprocess.run(
            ["systemctl", "show", f"{SERVICE_NAME}.service", "--property=LoadState"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and "LoadState=not-found" not in result.stdout
    except Exception:
        return False


def run_systemctl(*args, sudo=False):
    """Run a systemctl command, prefixing sudo when needed."""
    cmd = ["systemctl", *args]
    if sudo and os.geteuid() != 0:
        cmd = ["sudo", *cmd]
    return subprocess.run(cmd, capture_output=True, text=True)


def is_running():
    """Check if the systemd service is running."""
    try:
        result = run_systemctl("is-active", SERVICE_NAME)
        return result.stdout.strip() == "active"
    except Exception:
        return False


def get_status():
    """Get detailed service status (stdout + stderr)."""
    try:
        result = run_systemctl("status", SERVICE_NAME, "--no-pager")
        output = (result.stdout or "") + (result.stderr or "")
        return output.strip() or "No status available."
    except Exception as exc:
        return f"Error getting status: {exc}"


# --------------------------------------------------------------------------- #
# actions
# --------------------------------------------------------------------------- #

def _run_action(verb, past_tense):
    print(f"\n{verb.capitalize()}ing bot service...")
    try:
        result = run_systemctl(verb, SERVICE_NAME, sudo=True)
        if result.returncode == 0:
            print(f"Bot service {past_tense} successfully!")
        else:
            message = (result.stderr or result.stdout or "").strip()
            print(f"Failed to {verb}: {message or 'unknown error'}")
            return False
    except Exception as exc:
        print(f"Error trying to {verb} service: {exc}")
        return False

    time.sleep(1)
    state = "RUNNING" if is_running() else "NOT RUNNING"
    print(f"Current state: {state}")
    return True


def start_bot():
    return _run_action("start", "started")


def stop_bot():
    return _run_action("stop", "stopped")


def restart_bot():
    return _run_action("restart", "restarted")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main():
    command = sys.argv[1].strip().lower() if len(sys.argv) > 1 else ""

    if command in ("-h", "--help"):
        print(__doc__)
        return 0

    if command and command not in ("status", "start", "stop", "restart", "menu"):
        print(f"Unknown command: {command}")
        print("Use: status | start | stop | restart (or no argument for the menu)")
        return 1

    if not systemd_available():
        print("systemd is not available on this machine.")
        print("Run this on the Raspberry Pi where the bot is installed.")
        return 1

    if not unit_exists():
        print(f"Unit '{SERVICE_NAME}.service' was not found.")
        print("Install it with parcel-bot-pi/install.sh, or set the unit name:")
        print("  TRACKING_BOT_SERVICE=your-unit python3 tracking-bot-service-check.py")
        return 1

    if command == "status":
        running = is_running()
        print(f"Bot service is {'RUNNING' if running else 'NOT RUNNING'}")
        print(get_status())
        return 0 if running else 1

    if command in ("start", "stop", "restart"):
        action = {"start": start_bot, "stop": stop_bot, "restart": restart_bot}[command]
        return 0 if action() else 1

    if is_running():
        print("Bot service is RUNNING")
        print(get_status())

        print("\nOptions:")
        print("1. Stop")
        print("2. Restart")
        print("3. Exit")

        choice = input("\nEnter choice (1/2/3): ").strip()

        if choice == "1":
            stop_bot()
        elif choice == "2":
            restart_bot()
        else:
            print("Service continues running.")
    else:
        print("Bot service is NOT RUNNING")
        print(get_status())

        choice = input("\nDo you want to start the bot? (Y/N): ").strip().upper()
        if choice == "Y":
            start_bot()
        else:
            print("Bot not started.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
