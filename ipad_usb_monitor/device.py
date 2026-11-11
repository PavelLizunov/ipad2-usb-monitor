#!/usr/bin/env python3
"""Install the framebuffer VNC viewer into the running K94 RAM system."""
import hashlib
import base64
from pathlib import Path
import socket
import time

from .usb import run
from .settings import load


from .paths import ROOT as BASE, BUILD


def command(text):
    output, status = run(text)
    if status:
        raise RuntimeError(output)
    return output


def main():
    binary = (BUILD / "fbvnc-arm").read_bytes()
    expected = hashlib.sha256(binary).hexdigest()
    loop = (BASE / "device/k94-vnc-loop").read_bytes()
    loop_sha = hashlib.sha256(loop).hexdigest()
    settings = load()
    options = ("quality=" + str(settings["quality"]) + "\nrotation=" + str(settings["rotation"]) +
               "\nadaptive=" + str(settings["adaptive"]) + "\n").encode()
    options_sha = hashlib.sha256(options).hexdigest()
    model = command("cat /proc/device-tree/model; echo; uname -r")
    if model.splitlines()[0].rstrip("\x00") != "Apple iPad 2 GSM (K94AP)":
        raise RuntimeError("The connected Linux device is not K94AP")
    print(model.replace("\x00", ""), flush=True)
    present = command("""
if test -f /run/fbvnc-monitor.pid; then
    old=$(cat /run/fbvnc-monitor.pid)
    if test -f /run/k94-viewer-options && /bin/busybox grep -q /run/k94-vnc-loop /proc/"$old"/cmdline 2>/dev/null; then
        /bin/busybox sha256sum /run/fbvnc /run/k94-vnc-loop /run/k94-viewer-options
    fi
fi
""")
    hashes = [line.split()[0] for line in present.splitlines() if line.strip()]
    if hashes == [expected, loop_sha, options_sha]:
        print("Matching framebuffer viewer and reconnect supervisor already running", flush=True)
        return
    command("""
if test -f /run/fbvnc-monitor.pid; then
    old=$(cat /run/fbvnc-monitor.pid)
    if /bin/busybox grep -Eq '/run/(fbvnc|k94-vnc-loop)' /proc/"$old"/cmdline 2>/dev/null; then
        kill "$old"
        /bin/busybox pkill -f '^/run/fbvnc ' 2>/dev/null || true
    fi
fi
/bin/busybox pkill -f '^/bin/sh /run/k94-vnc-loop$' 2>/dev/null || true
/bin/busybox pkill -f '^/run/fbvnc ' 2>/dev/null || true
/bin/busybox timeout 30 /bin/busybox nc -l -s 10.94.0.2 -p 18996 </dev/null >/run/fbvnc 2>/run/fbvnc-transfer.log &
""")
    for attempt in range(30):
        try:
            connection = socket.create_connection(("10.94.0.2", 18996), timeout=3)
            break
        except OSError:
            if attempt == 29:
                raise
            time.sleep(.1)
    with connection:
        connection.settimeout(10)
        connection.sendall(binary)
        connection.shutdown(socket.SHUT_WR)
        while connection.recv(4096):
            pass
    output = command("/bin/busybox sha256sum /run/fbvnc")
    if output.split()[0] != expected:
        raise RuntimeError("Transferred viewer SHA256 mismatch")
    print("Framebuffer VNC viewer transferred and SHA256 verified", flush=True)
    encoded = base64.b64encode(loop).decode()
    command("printf %s " + encoded + " | /bin/busybox base64 -d >/run/k94-vnc-loop; /bin/busybox chmod 700 /run/k94-vnc-loop")
    encoded = base64.b64encode(options).decode()
    command("printf %s " + encoded + " | /bin/busybox base64 -d >/run/k94-viewer-options")
    command("""
/bin/busybox chmod 700 /run/fbvnc
for console in /sys/class/vtconsole/vtcon*/bind; do
    echo 0 > "$console"
done
setsid /run/k94-vnc-loop </dev/tty1 >/run/k94-vnc-loop.log 2>&1 &
""")
    print("Framebuffer VNC viewer started", flush=True)
    print(command("cat /run/fbvnc-monitor.pid"), flush=True)


if __name__ == "__main__":
    main()
