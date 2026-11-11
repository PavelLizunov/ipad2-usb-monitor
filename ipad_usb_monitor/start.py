#!/usr/bin/env python3
"""Start the K94 USB monitor, booting the prepared RAM image when needed."""
from datetime import datetime
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

from serial.tools import list_ports
from .device import main as install_display
from .settings import load


from .paths import ROOT as BASE, BOOT_KIT


def call(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    linux_ports = [p for p in list_ports.comports()
                   if (p.vid, p.pid) == (0x0525, 0xA4AA)]
    tunnel = None
    if len(linux_ports) > 1:
        raise RuntimeError("More than one Linux USB gadget is connected")
    try:
        if not linux_ports:
            sys.path.insert(0, str(BOOT_KIT / ".work/cascadia/lib"))
            import appleusb
            device = appleusb.find()
            args = [sys.executable, "-m", "ipad_usb_monitor.boot", "--boot", "--no-watchdog"]
            if device is not None and appleusb.Device(device).mode == "Recovery":
                args.append("--resume-recovery")
            else:
                ids = subprocess.check_output(["idevice_id", "-l"], text=True, timeout=10).splitlines()
                if len(ids) != 1:
                    raise RuntimeError("Connect exactly one iPad, unlock it, and confirm trust")
                with socket.socket() as probe:
                    try:
                        probe.bind(("127.0.0.1", 22222))
                    except OSError:
                        pass
                    else:
                        tunnel = "ipad2-k94-boot-ssh-" + datetime.now().strftime("%Y%m%d-%H%M%S")
                        call("systemd-run", "--user", "--unit=" + tunnel, "--collect", "--service-type=exec",
                             "/usr/bin/iproxy", "-u", ids[0], "-l", "-s", "127.0.0.1", "22222:22")
            print("Starting the K94 Linux RAM image. Carbon/OpenSSH must be active in iOS.", flush=True)
            call(*args, cwd=BASE, timeout=180)
    finally:
        if tunnel:
            subprocess.run(["systemctl", "--user", "stop", tunnel + ".service"], check=False)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for attempt in range(45):
        try:
            with opener.open("http://10.94.0.2:18994/status", timeout=2) as response:
                status = response.read(16384)
            if b"K94_USERSPACE_REACHED" not in status or b"Apple iPad 2 GSM (K94AP)" not in status:
                raise RuntimeError("Unexpected USB diagnostic device")
            break
        except OSError:
            if attempt == 44:
                raise RuntimeError("K94 USB networking did not become ready")
            time.sleep(1)
    call("systemctl", "--user", "start", "ipad2-k94-monitor.service", timeout=80)
    install_display()
    settings = load()
    print(f"iPad USB monitor ready: IPAD2, {settings['width']}x{settings['height']}, rotation {90 * settings['rotation']} degrees, scaled to the iPad screen.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc))
