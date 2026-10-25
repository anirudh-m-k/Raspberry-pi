#!/usr/bin/env python3
"""
Finance-Track Service Manager for Raspberry Pi
Manages systemd services: gunicorn, nginx, cloudflared, internet-online-notify
"""

import subprocess
import sys
import os
import time

# ── Service Definitions ──────────────────────────────────────────────
SERVICES = [
    {
        'name': 'fintrack-gunicorn',
        'unit': 'fintrack-gunicorn.service',
        'depends_on': [],
        'health_url': 'http://127.0.0.1:8000',
        'description': 'Gunicorn WSGI Server',
    },
    {
        'name': 'nginx',
        'unit': 'nginx.service',
        'depends_on': ['fintrack-gunicorn'],
        'description': 'Nginx Reverse Proxy',
    },
    {
        'name': 'cloudflared',
        'unit': 'cloudflared.service',
        'depends_on': ['nginx', 'fintrack-gunicorn'],
        'description': 'Cloudflare Tunnel',
    },
    {
        'name': 'internet-online-notify',
        'unit': 'internet-online-notify.service',
        'depends_on': [],
        'description': 'Discord Boot Notification',
    },
]

# ── Colors ───────────────────────────────────────────────────────────
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
DIM = '\033[2m'
RESET = '\033[0m'


def run(cmd, check=False):
    """Run a shell command and return output."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=10
    )
    if check and result.returncode != 0:
        return None
    return result.stdout.strip()


def sudo_run(cmd):
    """Run a command with sudo."""
    return run(f'sudo {cmd}')


def get_service_status(unit):
    """Get active state of a systemd unit."""
    output = run(f'systemctl is-active {unit}')
    return output if output else 'inactive'


def get_service_substate(unit):
    """Get sub-state of a systemd unit."""
    output = run(f'systemctl show {unit} --property=SubState --value')
    return output if output else 'unknown'


def get_service_pid(unit):
    """Get main PID of a service."""
    output = run(f'systemctl show {unit} --property=MainPID --value')
    return output if output and output != '0' else None


def get_service_uptime(unit):
    """Get elapsed time since the service started."""
    output = run(f'systemctl show {unit} --property=ActiveEnterTimestamp --value')
    if not output:
        return None
    try:
        from datetime import datetime
        start = datetime.strptime(output.strip(), '%a %Y-%m-%d %H:%M:%S %Z')
        delta = datetime.now() - start
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if days > 0:
            return f'{days}d {hours}h {minutes}m'
        elif hours > 0:
            return f'{hours}h {minutes}m'
        else:
            return f'{minutes}m'
    except Exception:
        return output.strip()


def get_service_memory(unit):
    """Get memory usage of a service."""
    pid = get_service_pid(unit)
    if not pid:
        return None
    output = run(f'ps -o rss= -p {pid}')
    if output:
        try:
            rss_kb = int(output.strip())
            if rss_kb > 1024:
                return f'{rss_kb / 1024:.1f} MB'
            return f'{rss_kb} KB'
        except ValueError:
            pass
    return None


def find_service(name):
    """Find a service definition by name."""
    for svc in SERVICES:
        if svc['name'] == name:
            return svc
    return None


# ── Display Functions ────────────────────────────────────────────────

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')


def print_header():
    print(f'\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════╗{RESET}')
    print(f'{BOLD}{CYAN}║       Finance-Track Service Manager (Raspberry Pi)   ║{RESET}')
    print(f'{BOLD}{CYAN}╚══════════════════════════════════════════════════════╝{RESET}\n')


def display_status():
    """Display status of all services."""
    print(f'{BOLD}Service Status{RESET}')
    print(f'{"─" * 60}')
    print(f'  {"Service":<28} {"Status":<12} {"PID":<8} {"Uptime":<10} {"Memory":<10}')
    print(f'{"─" * 60}')

    for svc in SERVICES:
        status = get_service_status(svc['unit'])
        pid = get_service_pid(svc['unit'])
        uptime = get_service_uptime(svc['unit'])
        memory = get_service_memory(svc['unit'])

        if status == 'active':
            dot = f'{GREEN}● Running{RESET}'
        elif status == 'activating':
            dot = f'{YELLOW}● Starting{RESET}'
        elif status == 'failed':
            dot = f'{RED}● Failed{RESET}'
        else:
            dot = f'{RED}● Stopped{RESET}'

        pid_str = pid if pid else '-'
        uptime_str = uptime if uptime else '-'
        memory_str = memory if memory else '-'

        print(f'  {svc["name"]:<28} {dot:<21} {pid_str:<8} {uptime_str:<10} {memory_str:<10}')

    print(f'{"─" * 60}\n')


def display_menu():
    """Display the main menu."""
    print(f'{BOLD}Options:{RESET}')
    print(f'  {CYAN}1{RESET}. Refresh status')
    print(f'  {CYAN}2{RESET}. Start all services')
    print(f'  {CYAN}3{RESET}. Stop all services')
    print(f'  {CYAN}4{RESET}. Restart all services (reboot app)')
    print(f'  {CYAN}5{RESET}. Restart Gunicorn only')
    print(f'  {CYAN}6{RESET}. View service logs')
    print(f'  {CYAN}7{RESET}. App health check')
    print(f'  {CYAN}8{RESET}. Start a specific service')
    print(f'  {CYAN}9{RESET}. Stop a specific service')
    print(f'  {CYAN}0{RESET}. Exit')
    print()


def choose_service(prompt="Select service"):
    """Let user choose a service."""
    print(f'{BOLD}{prompt}:{RESET}')
    for i, svc in enumerate(SERVICES, 1):
        print(f'  {CYAN}{i}{RESET}. {svc["name"]} ({svc["description"]})')
    print()

    while True:
        choice = input('Enter number: ').strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(SERVICES):
                return SERVICES[idx]
        except ValueError:
            pass
        print(f'{RED}Invalid choice. Try again.{RESET}')


# ── Service Operations ───────────────────────────────────────────────

def start_service(svc):
    """Start a single service."""
    print(f'  Starting {svc["name"]}...', end=' ', flush=True)
    output = sudo_run(f'systemctl start {svc["unit"]}')
    time.sleep(1)
    status = get_service_status(svc['unit'])
    if status == 'active':
        print(f'{GREEN}OK{RESET}')
        return True
    else:
        print(f'{RED}FAILED{RESET}')
        return False


def stop_service(svc):
    """Stop a single service."""
    print(f'  Stopping {svc["name"]}...', end=' ', flush=True)
    sudo_run(f'systemctl stop {svc["unit"]}')
    time.sleep(1)
    status = get_service_status(svc['unit'])
    if status != 'active':
        print(f'{GREEN}OK{RESET}')
        return True
    else:
        print(f'{RED}FAILED{RESET}')
        return False


def restart_service(svc):
    """Restart a single service."""
    print(f'  Restarting {svc["name"]}...', end=' ', flush=True)
    sudo_run(f'systemctl restart {svc["unit"]}')
    time.sleep(2)
    status = get_service_status(svc['unit'])
    if status == 'active':
        print(f'{GREEN}OK{RESET}')
        return True
    else:
        print(f'{RED}FAILED{RESET}')
        return False


def start_all():
    """Start all services in dependency order."""
    print(f'\n{BOLD}Starting all services (in order)...{RESET}')
    for svc in SERVICES:
        if get_service_status(svc['unit']) == 'active':
            print(f'  {svc["name"]}: {DIM}already running{RESET}')
        else:
            start_service(svc)
    print()


def stop_all():
    """Stop all services in reverse dependency order."""
    print(f'\n{BOLD}Stopping all services (reverse order)...{RESET}')
    for svc in reversed(SERVICES):
        if get_service_status(svc['unit']) != 'active':
            print(f'  {svc["name"]}: {DIM}already stopped{RESET}')
        else:
            stop_service(svc)
    print()


def restart_all():
    """Restart all services in dependency order."""
    print(f'\n{BOLD}Restarting all services (in order)...{RESET}')
    for svc in SERVICES:
        restart_service(svc)
    print()


def view_logs(svc, lines=30):
    """View recent logs for a service."""
    print(f'\n{BOLD}Logs for {svc["name"]} (last {lines} lines):{RESET}')
    print(f'{"─" * 60}')
    output = run(f'sudo journalctl -u {svc["unit"]} --no-pager -n {lines}')
    if output:
        print(output)
    else:
        print(f'{DIM}No logs available{RESET}')
    print(f'{"─" * 60}\n')


def health_check():
    """Check if the app responds on port 8000."""
    print(f'\n{BOLD}App Health Check{RESET}')
    print(f'{"─" * 60}')

    # Check Gunicorn
    gunicorn_status = get_service_status('fintrack-gunicorn.service')
    print(f'  Gunicorn: {"● Running" if gunicorn_status == "active" else "● Stopped"}')

    # Check Nginx
    nginx_status = get_service_status('nginx.service')
    print(f'  Nginx:    {"● Running" if nginx_status == "active" else "● Stopped"}')

    # Check Cloudflare
    cf_status = get_service_status('cloudflared.service')
    print(f'  Cloudflared: {"● Running" if cf_status == "active" else "● Stopped"}')

    # HTTP check
    print(f'\n  HTTP Check:')
    output = run('curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://127.0.0.1:8000')
    if output and output.isdigit():
        code = int(output)
        if code == 200:
            print(f'    localhost:8000 → {GREEN}HTTP {code} OK{RESET}')
        else:
            print(f'    localhost:8000 → {YELLOW}HTTP {code}{RESET}')
    else:
        print(f'    localhost:8000 → {RED}Connection failed{RESET}')

    output = run('curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://127.0.0.1:80')
    if output and output.isdigit():
        code = int(output)
        if code == 200:
            print(f'    localhost:80     → {GREEN}HTTP {code} OK{RESET}')
        else:
            print(f'    localhost:80     → {YELLOW}HTTP {code}{RESET}')
    else:
        print(f'    localhost:80     → {RED}Connection failed{RESET}')

    print(f'{"─" * 60}\n')


# ── Main Loop ────────────────────────────────────────────────────────

def main():
    # Check if running as root or with sudo access
    if os.geteuid() != 0:
        print(f'{YELLOW}Note: sudo access required for service management.{RESET}')
        print(f'{DIM}You may be prompted for your password.{RESET}\n')

    while True:
        clear_screen()
        print_header()
        display_status()
        display_menu()

        choice = input(f'{BOLD}Enter choice: {RESET}').strip()

        if choice == '1':
            pass  # Just refresh
        elif choice == '2':
            start_all()
        elif choice == '3':
            confirm = input(f'{YELLOW}Stop all services? (y/N): {RESET}').strip().lower()
            if confirm == 'y':
                stop_all()
        elif choice == '4':
            confirm = input(f'{YELLOW}Restart all services? (y/N): {RESET}').strip().lower()
            if confirm == 'y':
                restart_all()
        elif choice == '5':
            svc = find_service('fintrack-gunicorn')
            if svc:
                confirm = input(f'{YELLOW}Restart Gunicorn? (y/N): {RESET}').strip().lower()
                if confirm == 'y':
                    restart_service(svc)
        elif choice == '6':
            svc = choose_service("Choose service to view logs")
            if svc:
                view_logs(svc)
                input('Press Enter to continue...')
        elif choice == '7':
            health_check()
            input('Press Enter to continue...')
        elif choice == '8':
            svc = choose_service("Choose service to start")
            if svc:
                start_service(svc)
        elif choice == '9':
            svc = choose_service("Choose service to stop")
            if svc:
                confirm = input(f'{YELLOW}Stop {svc["name"]}? (y/N): {RESET}').strip().lower()
                if confirm == 'y':
                    stop_service(svc)
        elif choice == '0':
            print(f'\n{GREEN}Goodbye!{RESET}\n')
            sys.exit(0)
        else:
            print(f'{RED}Invalid choice.{RESET}')
            time.sleep(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f'\n\n{GREEN}Goodbye!{RESET}\n')
        sys.exit(0)
