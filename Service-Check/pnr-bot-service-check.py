import subprocess
import sys

SERVICE_NAME = "pnr-bot"


def is_running():
    """Check if the systemd service is running."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME],
            capture_output=True,
            text=True
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False


def get_status():
    """Get detailed service status."""
    try:
        result = subprocess.run(
            ["systemctl", "status", SERVICE_NAME],
            capture_output=True,
            text=True
        )
        return result.stdout
    except Exception as e:
        return f"Error getting status: {e}"


def start_bot():
    """Start the systemd service."""
    print("\nStarting bot service...")
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "start", SERVICE_NAME],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("Bot service started successfully!")
        else:
            print(f"Failed to start: {result.stderr}")
    except Exception as e:
        print(f"Error starting service: {e}")


def stop_bot():
    """Stop the systemd service."""
    print("\nStopping bot service...")
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "stop", SERVICE_NAME],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("Bot service stopped successfully!")
        else:
            print(f"Failed to stop: {result.stderr}")
    except Exception as e:
        print(f"Error stopping service: {e}")


def restart_bot():
    """Restart the systemd service."""
    print("\nRestarting bot service...")
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "restart", SERVICE_NAME],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("Bot service restarted successfully!")
        else:
            print(f"Failed to restart: {result.stderr}")
    except Exception as e:
        print(f"Error restarting service: {e}")


def main():
    """Main function to manage the bot service."""
    running = is_running()

    if running:
        print(f"Bot service is RUNNING")
        status = get_status()
        print(status)

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

        choice = input("\nDo you want to start the bot? (Y/N): ").strip().upper()
        if choice == "Y":
            start_bot()
        else:
            print("Bot not started.")


if __name__ == "__main__":
    main()
