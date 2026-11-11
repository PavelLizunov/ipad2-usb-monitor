import argparse
import fcntl
import subprocess

from .device import main as install_display
from .settings import BASE, load, save
from .paths import STATE

def main():
    parser = argparse.ArgumentParser(description="iPad USB monitor orientation and speed")
    parser.add_argument("action", choices=("rotate", "landscape", "portrait", "native", "balanced", "fast", "quality", "status"))
    parser.add_argument("value", nargs="?", type=int)
    args = parser.parse_args()
    with (STATE / "monitor-control.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        settings = load()
        if args.action == "status":
            print(settings)
            raise SystemExit(0)
        if args.action == "rotate":
            settings["rotation"] = (settings["rotation"] + 1) % 4
        elif args.action in ("landscape", "portrait"):
            settings["rotation"] = int(args.action == "portrait")
        elif args.action in ("native", "balanced", "fast"):
            width, height = {"native": (1024,768), "balanced": (800,600), "fast": (640,480)}[args.action]
            settings.update(width=width, height=height, quality={"native":6, "balanced":6, "fast":2}[args.action], adaptive=int(args.action != "fast"))
        elif args.action == "quality":
            if args.value is None or not 0 <= args.value <= 10:
                parser.error("quality requires 0..9 for JPEG or 10 for lossless")
            settings["quality"] = args.value
            settings["adaptive"] = 0
        save(settings)
        subprocess.run(["systemctl", "--user", "restart", "ipad2-k94-monitor.service"], check=True, timeout=80)
        install_display()
        print(settings)


if __name__ == "__main__":
    main()
