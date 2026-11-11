"""Install task-owned host integration; use --user-only on a prepared host."""
import argparse
import getpass
import json
from pathlib import Path
import re
import shutil
import subprocess

from .paths import ROOT, STATE
from .settings import SETTINGS, load, save


def run(*args):
    return subprocess.run([str(a) for a in args], check=True)


def managed(path, name, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_text() if path.exists() else ""
    start, end = "-- >>> " + name, "-- <<< " + name
    current = re.sub(re.escape(start) + r"\n.*?" + re.escape(end) + r"\n?", "", current, flags=re.S)
    path.write_text(current.rstrip() + "\n\n" + start + "\n" + content + "\n" + end + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boot-kit", type=Path)
    parser.add_argument("--user-only", action="store_true")
    args = parser.parse_args()
    if args.boot_kit:
        kit = args.boot_kit.expanduser().resolve()
        if not (kit / "bootchain-manifest.json").exists():
            raise RuntimeError("The boot kit has no bootchain-manifest.json")
        (STATE / "boot-kit-path").write_text(str(kit) + "\n")
    if not SETTINGS.exists():
        save(load())
    if not (ROOT / ".build/fbvnc-arm").exists():
        run(ROOT / ".venv/bin/python", ROOT / "tools/build_viewer.py")
    if not args.user_only:
        run("sudo", "install", "-m", "644", ROOT / "udev/10-ipad2-k94.link", "/etc/systemd/network/10-ipad2-k94.link")
        rules = (ROOT / "udev/60-ipad2-k94.rules.in").read_text().replace("@USER@", getpass.getuser())
        generated = STATE / "60-ipad2-k94.rules"
        generated.write_text(rules)
        run("sudo", "install", "-m", "644", generated, "/etc/udev/rules.d/60-ipad2-k94.rules")
        run("sudo", "udevadm", "control", "--reload")
        profile = subprocess.run(["nmcli", "connection", "show", "ipad2-k94-usb"], capture_output=True)
        if profile.returncode:
            run("sudo", "nmcli", "connection", "add", "type", "ethernet", "con-name", "ipad2-k94-usb", "ifname", "ipad2",
                "802-3-ethernet.mac-address", "02:94:00:00:00:01", "ipv4.method", "manual", "ipv4.addresses", "10.94.0.1/30",
                "ipv4.never-default", "yes", "ipv6.method", "link-local", "ipv6.never-default", "yes", "connection.autoconnect", "yes")
        if shutil.which("ufw"):
            firewall = subprocess.run(["sudo", "ufw", "status"], capture_output=True, text=True, check=True)
            if "Status: active" in firewall.stdout:
                run("sudo", "ufw", "allow", "in", "on", "ipad2", "from", "10.94.0.2", "to", "10.94.0.1", "port", "5904", "proto", "tcp", "comment", "ipad2-k94-usb-vnc")
        run("sudo", "systemctl", "start", "usbmuxd.service")
    service = (ROOT / "systemd/ipad2-k94-monitor.service.in").read_text()
    service = service.replace("@ROOT@", str(ROOT)).replace("@PYTHON@", str(ROOT / ".venv/bin/python"))
    unit = Path.home() / ".config/systemd/user/ipad2-k94-monitor.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text(service)
    hypr = Path.home() / ".config/hypr"
    if hypr.exists():
        state_path = json.dumps(str(SETTINGS), ensure_ascii=False)
        lua = '''do
  local width, height, rotation = 1024, 768, 0
  local file = io.open(STATE_PATH, "r")
  if file then
    local data = file:read("*a")
    file:close()
    width = tonumber(data:match('"width"%s*:%s*(%d+)')) or width
    height = tonumber(data:match('"height"%s*:%s*(%d+)')) or height
    rotation = tonumber(data:match('"rotation"%s*:%s*(%d+)')) or rotation
  end
  if rotation % 2 == 1 then width, height = height, width end
  hl.monitor({ output="IPAD2", mode=width .. "x" .. height .. "@60", position="auto-right", scale=1, transform=0 })
end'''.replace("STATE_PATH", state_path)
        managed(hypr / "monitors.lua", "ipad2-usb-monitor", lua)
        listing = subprocess.run(["hyprctl", "-i", "0", "binds", "-j"], capture_output=True, text=True)
        if listing.returncode == 0:
            conflicts = [bind for bind in json.loads(listing.stdout) if bind.get("key") == "F8" and bind.get("modmask") == 64
                         and bind.get("description") != "Повернуть экран iPad"]
            if not conflicts:
                command = json.dumps(str(ROOT / "ipad-monitor") + " rotate", ensure_ascii=False)
                managed(hypr / "bindings.lua", "ipad2-usb-monitor", 'o.bind("SUPER + F8", "Повернуть экран iPad", ' + command + ')')
            run("hyprctl", "-i", "0", "reload")
            errors = subprocess.check_output(["hyprctl", "-i", "0", "configerrors"], text=True).strip()
            if errors:
                raise RuntimeError(errors)
    launcher = Path.home() / ".local/bin/ipad-monitor"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    if launcher.is_symlink() and launcher.resolve() == ROOT / "ipad-monitor":
        pass
    elif launcher.exists() or launcher.is_symlink():
        print("Existing launcher preserved:", launcher)
    else:
        launcher.symlink_to(ROOT / "ipad-monitor")
    run("systemctl", "--user", "daemon-reload")
    run("systemctl", "--user", "enable", "ipad2-k94-monitor.service")
    run("systemctl", "--user", "restart", "--no-block", "ipad2-k94-monitor.service")
    print("Installed. Start the attached iPad monitor with:", ROOT / "ipad-monitor", "start")


if __name__ == "__main__":
    main()
