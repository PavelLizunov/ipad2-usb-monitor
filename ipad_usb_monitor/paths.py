import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / ".build"
STATE = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "ipad2-usb-monitor"
STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
kit_file = STATE / "boot-kit-path"
BOOT_KIT = Path(os.environ.get("K94_BOOT_KIT", kit_file.read_text().strip() if kit_file.exists() else str(Path.home() / "Work/ipad2-k94"))).expanduser()
