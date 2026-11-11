import subprocess
import sys


def main():
    try:
        action = sys.argv[1] if len(sys.argv) > 1 else "start"
        if action == "start":
            from .start import main as start
            start()
        elif action == "stop":
            subprocess.run(["systemctl", "--user", "stop", "ipad2-k94-monitor.service"], check=True)
        else:
            from .control import main as control
            control()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
