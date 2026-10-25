#!/usr/bin/env python3
"""
Finance-Track Service Check & Management Tool
================================================================================
USAGE & COMMAND SYNTAX:

1. Interactive Menu Mode:
   python3 service_check.py
   - Description: Launches the interactive CLI menu to check status, perform 
     actions on individual/all services, or restart the web application.

2. Display Status Only:
   python3 service_check.py status
   # OR: python3 service_check.py --status (or -s)
   - Description: Displays current status, active/sub state, and recent logs (if
     failing) for all configured Raspberry Pi services without entering menu.

3. Start All Services:
   python3 service_check.py start
   # OR: python3 service_check.py --start
   - Description: Starts all services in dependency order.

4. Stop All Services:
   python3 service_check.py stop
   # OR: python3 service_check.py --stop
   - Description: Stops all services in reverse order.

5. Restart Web Application Stack:
    python3 service_check.py restart
    # OR: python3 service_check.py --restart (or -r)
    - Description: Restarts the web application runtime stack in correct sequence:
      Stops: Cloudflared -> Nginx -> Gunicorn
      Starts: Gunicorn -> Nginx -> Cloudflared

6. Update & Restart (Stop → Pull → Start):
    python3 service_check.py update
    # OR: python3 service_check.py --update
    - Description: Stops web app services only (gunicorn→nginx→cloudflared,
      excludes internet-online-notify.service which is one-shot/boot-only),
      verifies current branch is 'main' in /home/anirudh/Finance-Track
      (fallback to repo root), backs up instance/ (DB files), fetches &
      merges origin/main (ff-only, fallback to pull), restores instance/
      from backup to preserve DBs, then starts web app services in order
      (gunicorn→nginx→cloudflared).
================================================================================
"""
import argparse
import subprocess
import sys
import os
import time

# List of services configured for Raspberry Pi Finance-Track
SERVICES = [
    {
        "id": 1,
        "name": "internet-online-notify.service",
        "label": "Discord Boot Notification",
        "is_oneshot": True
    },
    {
        "id": 2,
        "name": "fintrack-gunicorn.service",
        "label": "Gunicorn WSGI Application Server",
        "is_oneshot": False
    },
    {
        "id": 3,
        "name": "nginx.service",
        "label": "Nginx Reverse Proxy",
        "is_oneshot": False
    },
    {
        "id": 4,
        "name": "cloudflared.service",
        "label": "Cloudflare Tunnel",
        "is_oneshot": False
    }
]

# Correct startup sequence for web application stack (Backend -> Reverse Proxy -> Public Tunnel)
WEB_APP_ORDER = [
    "fintrack-gunicorn.service",
    "nginx.service",
    "cloudflared.service"
]

# Terminal ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'


def run_sudo_cmd(cmd_args):
    """Executes a systemctl or service command using sudo if not running as root."""
    if os.geteuid() != 0:
        full_cmd = ['sudo'] + cmd_args
    else:
        full_cmd = cmd_args
    return subprocess.run(full_cmd, capture_output=True, text=True)


def check_service(svc_info):
    """Check detailed status of a service."""
    service = svc_info["name"]
    try:
        show_res = subprocess.run(
            ['systemctl', 'show', service, '--property=ActiveState,SubState'],
            capture_output=True,
            text=True
        )

        state_dict = {}
        for line in show_res.stdout.splitlines():
            if '=' in line:
                key, val = line.split('=', 1)
                state_dict[key] = val

        active_state = state_dict.get('ActiveState', 'unknown')
        sub_state = state_dict.get('SubState', 'unknown')

        is_running = False

        if active_state == 'active':
            is_running = True
        elif active_state == 'inactive' and sub_state == 'dead' and svc_info.get('is_oneshot'):
            fail_check = subprocess.run(
                ['systemctl', 'is-failed', service],
                capture_output=True,
                text=True
            ).stdout.strip()

            if fail_check != 'failed':
                is_running = True

        logs = ""
        if not is_running:
            # Fetch the last 10 lines of logs for the service to diagnose issues
            logs_res = subprocess.run(
                ['journalctl', '-u', service, '-n', '10', '--no-pager'],
                capture_output=True,
                text=True
            )
            logs = logs_res.stdout.strip()
            if not logs:
                status_res = subprocess.run(
                    ['systemctl', 'status', service, '--no-pager'],
                    capture_output=True,
                    text=True
                )
                logs = status_res.stdout.strip()

        return is_running, active_state, sub_state, logs

    except Exception as e:
        return False, 'error', 'error', f"Exception checking status: {str(e)}"


def display_all_services_status():
    """Display status of all services numbered clearly."""
    print("=" * 60)
    print(f"{BOLD}{CYAN}Current Raspberry Pi Services Status{RESET}")
    print("=" * 60)

    for svc in SERVICES:
        is_running, active_state, sub_state, logs = check_service(svc)
        status_str = f"{GREEN}Running{RESET}" if is_running else f"{RED}Not Running{RESET}"

        print(f"{BOLD}[Service {svc['id']}]{RESET} {CYAN}{svc['name']}{RESET} ({svc['label']})")
        print(f"   Status: {status_str} ({active_state}/{sub_state})")

        if not is_running and logs:
            print(f"   {YELLOW}Recent Issue / Logs:{RESET}")
            for line in logs.splitlines():
                print(f"     {line}")
        print("-" * 60)


def manage_service_action(action, service_name):
    """Start, stop, or restart a specific service unit."""
    action_verb = action.capitalize()
    print(f"-> Performing {BOLD}{action_verb}{RESET} on {CYAN}{service_name}{RESET}...")
    res = run_sudo_cmd(['systemctl', action, service_name])

    time.sleep(1)

    svc_info = next((s for s in SERVICES if s['name'] == service_name), {'name': service_name, 'is_oneshot': False})
    is_running, active_state, sub_state, _ = check_service(svc_info)

    if res.returncode == 0:
        print(f"   {GREEN}Success:{RESET} {action_verb} request sent. Current state: {active_state} ({sub_state})")
    else:
        print(f"   {RED}Error:{RESET} Failed to {action} {service_name}.")
        if res.stderr:
            print(f"   {res.stderr.strip()}")


def start_all_services():
    """Start all services in dependency order."""
    print(f"\n{BOLD}{GREEN}Starting all services in order...{RESET}\n")
    all_service_names = [s['name'] for s in SERVICES]
    for svc_name in all_service_names:
        manage_service_action('start', svc_name)


def stop_all_services():
    """Stop all services in reverse order."""
    print(f"\n{BOLD}{YELLOW}Stopping all services...{RESET}\n")
    all_service_names = [s['name'] for s in SERVICES]
    reverse_order = list(reversed(all_service_names))
    for svc_name in reverse_order:
        manage_service_action('stop', svc_name)


def restart_entire_web_app():
    """Restart the entire web application stack in the correct dependency order."""
    print("\n" + "=" * 60)
    print(f"{BOLD}{YELLOW}Restarting Entire Web Application Stack in Correct Sequence{RESET}")
    print("=" * 60)

    # Step 1: Stop services in reverse dependency order
    reverse_order = list(reversed(WEB_APP_ORDER))
    print(f"{BOLD}Phase 1: Stopping web application services...{RESET}")
    for svc_name in reverse_order:
        manage_service_action('stop', svc_name)

    print("\nWaiting 2 seconds before starting stack...\n")
    time.sleep(2)

    # Step 2: Start services in correct dependency order
    print(f"{BOLD}Phase 2: Starting web application services in dependency order...{RESET}")
    for svc_name in WEB_APP_ORDER:
        manage_service_action('start', svc_name)

    print("\n" + "=" * 60)
    print(f"{GREEN}{BOLD}Web Application Stack Restart Completed!{RESET}")
    print("=" * 60 + "\n")


def update_and_restart():
    """Stop services, pull latest code (excluding instance/), then restart."""
    REPO_PATH = "/home/anirudh/Finance-Track"

    print("\n" + "=" * 60)
    print(f"{BOLD}{CYAN}Update & Restart — Pull Latest Code + Restart Stack{RESET}")
    print("=" * 60)
    print(f"  Repo: {CYAN}{REPO_PATH}{RESET}")

    if not os.path.isdir(os.path.join(REPO_PATH, ".git")):
        print(f"{RED}Error:{RESET} Not a git repository: {REPO_PATH}")
        return

    # 1. Check current branch is main
    try:
        branch_res = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_PATH, capture_output=True, text=True
        )
        current_branch = branch_res.stdout.strip()
    except Exception as e:
        print(f"{RED}Error checking branch:{RESET} {e}")
        return

    print(f"  Current branch: {BOLD}{current_branch}{RESET}")
    if current_branch != "main":
        print(f"{RED}Aborted:{RESET} Current branch is '{current_branch}', expected 'main'.")
        print(f"  Switch to main first: {CYAN}git -C {REPO_PATH} checkout main{RESET}")
        return

    # 2. Stop only web app stack (not the one-shot boot notification)
    print(f"\n{BOLD}Phase 1: Stopping web application services...{RESET}")
    for svc_name in reversed(WEB_APP_ORDER):
        manage_service_action('stop', svc_name)

    # 3. Backup instance/ (contains db files) before pull
    instance_path = os.path.join(REPO_PATH, "instance")
    backup_root = None
    if os.path.isdir(instance_path):
        import tempfile, shutil
        backup_root = tempfile.mkdtemp(prefix="fintrack_instance_backup_")
        try:
            # Copy entire instance tree to temp backup
            shutil.copytree(instance_path, os.path.join(backup_root, "instance"), dirs_exist_ok=True)
            print(f"{GREEN}Backup:{RESET} instance/ → {backup_root}/instance")
        except Exception as e:
            print(f"{YELLOW}Warning:{RESET} Could not backup instance/: {e}")
            backup_root = None
    else:
        print(f"{YELLOW}Note:{RESET} No instance/ directory to preserve.")

    # 3b. Stash local changes so pull doesn't fail on dirty/untracked files
    # Covers: instance/finance_track.db (modified tracked) and any untracked
    # files like Service-running/service-check.py that would be overwritten.
    stashed = False
    try:
        stash_res = subprocess.run(
            ["git", "stash", "push", "--include-untracked", "-m", f"fintrack-auto-update-{int(time.time())}"],
            cwd=REPO_PATH, capture_output=True, text=True
        )
        # "No local changes to save" means nothing stashed
        if stash_res.returncode == 0 and "No local changes" not in stash_res.stdout:
            stashed = True
            print(f"{GREEN}Stash:{RESET} local changes stashed (dirty + untracked) for clean pull.")
        elif stash_res.returncode == 0:
            print(f"{CYAN}Stash:{RESET} working tree clean, nothing to stash.")
        else:
            print(f"{YELLOW}Stash warning:{RESET} {stash_res.stderr.strip() or stash_res.stdout.strip()}")
    except Exception as e:
        print(f"{YELLOW}Stash warning:{RESET} {e}")

    # 4. Pull latest code
    print(f"\n{BOLD}Phase 2: Pulling latest code from origin/main (preserving instance/)...{RESET}")
    pull_ok = False
    try:
        # Use fetch + merge to get clearer errors; instance restore happens regardless
        fetch_res = subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=REPO_PATH, capture_output=True, text=True
        )
        if fetch_res.returncode != 0:
            print(f"{RED}git fetch failed:{RESET}\n{fetch_res.stderr.strip()}")
            raise RuntimeError("fetch failed")

        pull_res = subprocess.run(
            ["git", "merge", "--ff-only", "origin/main"],
            cwd=REPO_PATH, capture_output=True, text=True
        )
        # Fallback to pull if ff-only not possible (e.g., diverged)
        if pull_res.returncode != 0:
            print(f"{YELLOW}Fast-forward not possible, trying git pull...{RESET}")
            pull_res = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=REPO_PATH, capture_output=True, text=True
            )

        if pull_res.returncode == 0:
            out = (pull_res.stdout or "").strip()
            print(f"{GREEN}Pull successful:{RESET} {out[:400] if out else 'Already up to date.'}")
            pull_ok = True
        else:
            print(f"{RED}git pull/merge failed:{RESET}\n{pull_res.stderr.strip() or pull_res.stdout.strip()}")
            raise RuntimeError("pull failed")

    except Exception as e:
        print(f"{RED}Error during git pull:{RESET} {e}")
        # Continue to restore instance even on failure
    finally:
        # 5. Restore instance/ from backup (overwrite anything pulled) — DB preservation
        if backup_root and os.path.isdir(os.path.join(backup_root, "instance")):
            try:
                import shutil
                # Remove pulled instance and restore original
                if os.path.isdir(instance_path):
                    shutil.rmtree(instance_path)
                shutil.copytree(os.path.join(backup_root, "instance"), instance_path, dirs_exist_ok=True)
                print(f"{GREEN}Restore:{RESET} instance/ restored from backup (DB files preserved).")
                shutil.rmtree(backup_root, ignore_errors=True)
            except Exception as e:
                print(f"{RED}Failed to restore instance/:{RESET} {e}")
                print(f"  Backup kept at: {backup_root}")

        # 5b. Drop the auto-stash — we already restored instance from backup,
        # and untracked files like Service-running/service-check.py should stay
        # at the pulled remote version (not the pre-pull local copy).
        if stashed:
            try:
                drop_res = subprocess.run(
                    ["git", "stash", "drop"],
                    cwd=REPO_PATH, capture_output=True, text=True
                )
                if drop_res.returncode == 0:
                    print(f"{GREEN}Stash:{RESET} auto-stash dropped (remote version kept).")
                else:
                    print(f"{YELLOW}Stash drop note:{RESET} {drop_res.stderr.strip() or drop_res.stdout.strip()}")
            except Exception as e:
                print(f"{YELLOW}Stash drop warning:{RESET} {e}")

    # 6. Start only web app stack in correct order
    print(f"\n{BOLD}Phase 3: Starting web application services...{RESET}")
    # Small pause to let filesystem settle
    time.sleep(1)
    for svc_name in WEB_APP_ORDER:
        manage_service_action('start', svc_name)

    print("\n" + "=" * 60)
    print(f"{GREEN}{BOLD}Update & Restart Completed!{RESET}")
    print("=" * 60 + "\n")


def menu_loop():
    """Interactive CLI menu loop."""
    while True:
        display_all_services_status()

        print(f"\n{BOLD}Select an Option:{RESET}")
        print(f"  {CYAN}1{RESET}. Action on Individual Service (Select by Service Number 1-{len(SERVICES)})")
        print(f"  {CYAN}2{RESET}. Action on ALL Services (Start / Stop / Restart All)")
        print(f"  {CYAN}3{RESET}. Restart Entire Web Application (Correct sequence: Gunicorn -> Nginx -> Cloudflared)")
        print(f"  {CYAN}4{RESET}. Refresh Status")
        print(f"  {CYAN}5{RESET}. Update & Restart (Stop web app → Pull main excluding instance/ → Start web app)")
        print(f"  {CYAN}0{RESET}. Exit")

        choice = input(f"\n{BOLD}Enter choice [0-5]: {RESET}").strip()

        if choice == '1':
            print("\nChoose Service Number:")
            for svc in SERVICES:
                print(f"  {CYAN}{svc['id']}{RESET}. {svc['name']} ({svc['label']})")

            svc_choice = input(f"Enter service number [1-{len(SERVICES)}]: ").strip()
            selected_svc = next((s for s in SERVICES if str(s['id']) == svc_choice), None)

            if not selected_svc:
                print(f"{RED}Invalid service number!{RESET}\n")
                time.sleep(1)
                continue

            print(f"\nSelected: {BOLD}{selected_svc['name']}{RESET}")
            print("Select Action:")
            print(f"  {CYAN}1{RESET}. Restart")
            print(f"  {CYAN}2{RESET}. Stop")
            print(f"  {CYAN}3{RESET}. Start")
            act_choice = input("Enter action choice [1-3]: ").strip()

            action_map = {'1': 'restart', '2': 'stop', '3': 'start'}
            if act_choice in action_map:
                action = action_map[act_choice]
                manage_service_action(action, selected_svc['name'])
            else:
                print(f"{RED}Invalid action choice!{RESET}")

            input(f"\n{BOLD}Press Enter to continue...{RESET}")

        elif choice == '2':
            print("\nSelect Action for ALL Services:")
            print(f"  {CYAN}1{RESET}. Restart ALL Services")
            print(f"  {CYAN}2{RESET}. Stop ALL Services")
            print(f"  {CYAN}3{RESET}. Start ALL Services")
            act_choice = input("Enter action choice [1-3]: ").strip()

            if act_choice == '1':
                confirm = input(f"{YELLOW}Are you sure you want to RESTART ALL services? (y/N): {RESET}").strip().lower()
                if confirm == 'y':
                    stop_all_services()
                    time.sleep(1)
                    start_all_services()
            elif act_choice == '2':
                confirm = input(f"{YELLOW}Are you sure you want to STOP ALL services? (y/N): {RESET}").strip().lower()
                if confirm == 'y':
                    stop_all_services()
            elif act_choice == '3':
                confirm = input(f"{YELLOW}Are you sure you want to START ALL services? (y/N): {RESET}").strip().lower()
                if confirm == 'y':
                    start_all_services()
            else:
                print(f"{RED}Invalid action choice!{RESET}")

            input(f"\n{BOLD}Press Enter to continue...{RESET}")

        elif choice == '3':
            confirm = input(f"{YELLOW}Are you sure you want to restart the entire web application stack in sequence? (y/N): {RESET}").strip().lower()
            if confirm == 'y':
                restart_entire_web_app()
            input(f"\n{BOLD}Press Enter to continue...{RESET}")

        elif choice == '4':
            print("\nRefreshing status...")
            time.sleep(0.5)

        elif choice == '5':
            confirm = input(f"{YELLOW}This will STOP web app (gunicorn/nginx/cloudflared), pull origin/main (preserving instance/), then START web app. Continue? (y/N): {RESET}").strip().lower()
            if confirm == 'y':
                update_and_restart()
            input(f"\n{BOLD}Press Enter to continue...{RESET}")

        elif choice == '0':
            print(f"\n{GREEN}Exiting Service Manager. Goodbye!{RESET}\n")
            sys.exit(0)

        else:
            print(f"\n{RED}Invalid selection. Please try again.{RESET}\n")
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(
        description="Raspberry Pi Finance-Track Service Check & Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 service_check.py                  # Interactive menu mode
  python3 service_check.py status           # Display status only
  python3 service_check.py start            # Start all services in order
  python3 service_check.py stop             # Stop all services in reverse order
  python3 service_check.py restart          # Restart web application stack in sequence
  python3 service_check.py update           # Stop, pull main (preserve instance/), start all
"""
    )

    parser.add_argument(
        "command",
        nargs="?",
        choices=["status", "start", "stop", "restart", "update"],
        help="Command action: status, start, stop, restart, or update"
    )
    parser.add_argument(
        "-s", "--status",
        action="store_true",
        help="Display status of all services and exit"
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start all services in order"
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop all services in reverse order"
    )
    parser.add_argument(
        "-r", "--restart",
        action="store_true",
        help="Restart entire web application stack in sequence"
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Stop web app, pull origin/main preserving instance/, then start web app"
    )

    args = parser.parse_args()

    action = args.command
    if args.status:
        action = "status"
    elif args.start:
        action = "start"
    elif args.stop:
        action = "stop"
    elif args.restart:
        action = "restart"
    elif args.update:
        action = "update"

    if action == "status":
        display_all_services_status()
    elif action == "start":
        start_all_services()
    elif action == "stop":
        stop_all_services()
    elif action == "restart":
        restart_entire_web_app()
    elif action == "update":
        update_and_restart()
    else:
        menu_loop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{GREEN}Exiting Service Manager. Goodbye!{RESET}\n")
        sys.exit(0)
