#!/usr/bin/env python3
"""Validate a K94 RAM bundle; --boot performs one bounded USB boot test.

Requires this experiment's prepared Cascadia checkout, iOS SSH key and
verified kloader. Does not restore firmware or flash internal storage.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


from .paths import BOOT_KIT
BASE = BOOT_KIT
WORK = BASE / ".work"
CAS = WORK / "cascadia"
A5 = CAS / "devices/a5"
KLOADER_SHA = "bec212b4d99a1e3b9fa4add663fa884a2435045d1e47051415f4e26e197f8132"


def checked_file(path, digest):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError(f"SHA256 mismatch: {path.name}")
    return data


def ssh(command, **kwargs):
    return subprocess.run([
        "ssh", "-i", str(WORK / "ios-root-key"), "-p", "22222",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
        "-o", "HostKeyAlgorithms=+ssh-rsa",
        "-o", "UserKnownHostsFile=" + str(WORK / "ios-known-hosts"),
        "root@127.0.0.1", command,
    ], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boot", action="store_true", help="Actually leave iOS and test RAM boot")
    parser.add_argument("--no-watchdog", action="store_true", help="Select the diagnostic bundle without automatic reset")
    parser.add_argument("--skip-serial", action="store_true", help="Leave the macOS ACM port closed; use USB network diagnostics")
    parser.add_argument("--resume-recovery", action="store_true", help="Continue --boot from Recovery using the saved paired iPad identity")
    args = parser.parse_args()
    if args.resume_recovery and not args.boot:
        parser.error("--resume-recovery requires --boot")
    bundle_dir = A5 / ("build/k94/bundle-diag-v2" if args.no_watchdog else "build/k94/bundle-diag-v8-wdt120")
    receipt = json.loads((bundle_dir / "manifest.json").read_text())
    expected_watchdog = None if args.no_watchdog else 120
    if receipt["board"] != "K94AP" or receipt.get("watchdog_timeout_seconds") != expected_watchdog:
        raise RuntimeError("Unexpected board/watchdog configuration")
    for name, entry in receipt["files"].items():
        if Path(name).name != name:
            raise RuntimeError("Invalid manifest filename")
        checked_file(bundle_dir / name, entry["sha256"])
    bundle = (bundle_dir / "staging-bundle.bin").read_bytes()
    if len(bundle) > 12 * 1024 * 1024:
        raise RuntimeError("Bundle exceeds first-test Recovery transfer budget")
    stock = json.loads((BASE / "bootchain-manifest.json").read_text())
    chain = A5 / "build/k94/bootchain-v2"
    ibss = checked_file(chain / "iBSS.sigpatched", stock["iBSS.sigpatched"])
    ibec = checked_file(chain / "iBEC.autogo.plain.dfu", stock["iBEC.autogo.plain.dfu"])
    if ibss[:4] != bytes.fromhex("0e0000ea"):
        raise RuntimeError("Expected raw ARM iBSS")
    loader = checked_file(WORK / "kloader", KLOADER_SHA)
    config_path = "build/out/kernel-config" if args.no_watchdog else "build/k94/kernel-trace-late/kernel-config"
    config = (A5 / config_path).read_text().splitlines()
    if any(x in config for x in ("CONFIG_MTD=y", "CONFIG_DRM_APPLE_SGX=y", "CONFIG_HFSPLUS_FS=y")):
        raise RuntimeError("Unexpected storage/GPU config")
    print(f"Verified K94AP bootchain and {len(bundle)}-byte RAM bundle", flush=True)
    if not args.boot:
        return

    # The USB identity is acquired from the paired device, then checked again
    # in each DFU/Recovery session before sending any image.
    def info(key):
        return subprocess.check_output(["ideviceinfo", "-k", key], text=True).strip()
    if args.resume_recovery:
        saved = json.loads((WORK / "k94-ios-identity.json").read_text())
        if saved["board"] != "K94AP":
            raise RuntimeError("Saved identity is not K94AP")
        ecid = int(saved["ecid"])
    else:
        if (info("ProductType"), info("HardwareModel"), info("ChipID"), info("BoardId")) != (
            "iPad2,2", "K94AP", "35136", "6",
        ):
            raise RuntimeError("Connected device is not iPad2,2 / K94AP")
        ecid = int(info("UniqueChipID"))
        (WORK / "k94-ios-identity.json").write_text(json.dumps({"ecid": ecid, "board": "K94AP"}) + "\n")
        if ssh("sysctl -n hw.machine", capture_output=True, text=True).stdout.strip() != "iPad2,2":
            raise RuntimeError("SSH target is not iPad2,2")
        ssh("umask 077; mkdir -p /tmp/homelab-k94-linux; cat > /tmp/homelab-k94-linux/kloader; chmod 755 /tmp/homelab-k94-linux/kloader", input=loader)
        ssh("cat > /tmp/homelab-k94-linux/ibss", input=ibss)

    sys.path.insert(0, str(CAS / "lib"))
    import appleusb
    import serial
    from serial.tools import list_ports

    def device(mode, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            candidate = appleusb.find()
            if candidate is not None:
                target = appleusb.Device(candidate)
                if target.mode != mode or not all(target.info.get(key) for key in ("CPID", "BDID", "ECID")):
                    target.close()
                    time.sleep(.3)
                    continue
                fields = target.info
                if (int(fields.get("CPID", "-1"), 16), int(fields.get("BDID", "-1"), 16),
                        int(fields.get("ECID", "-1"), 16)) != (0x8940, 6, ecid):
                    raise RuntimeError("DFU/Recovery device identity mismatch")
                if target.mode == mode:
                    return target.claim()
            time.sleep(.3)
        raise RuntimeError(f"Expected {mode} USB mode did not appear")

    if not args.resume_recovery:
        print("Starting kloader; iOS will leave USB", flush=True)
        ssh_args = ["ssh", "-i", str(WORK / "ios-root-key"), "-p", "22222",
                    "-o", "BatchMode=yes", "-o", "HostKeyAlgorithms=+ssh-rsa",
                    "-o", "UserKnownHostsFile=" + str(WORK / "ios-known-hosts"),
                    "root@127.0.0.1", "/tmp/homelab-k94-linux/kloader /tmp/homelab-k94-linux/ibss"]
        with (WORK / "kloader-boot.log").open("wb") as log:
            launch = subprocess.Popen(ssh_args, stdout=log, stderr=subprocess.STDOUT)
            try:
                target = device("DFU", 60)
            finally:
                if launch.poll() is None:
                    launch.terminate()
                launch.wait(timeout=5)
        print("K94 DFU identity verified; sending plaintext patched iBEC", flush=True)
        try:
            target.send(ibec, progress=False)
        finally:
            target.close()
    target = device("Recovery", 20)
    print("K94 Recovery identity verified; sending RAM bundle", flush=True)
    try:
        target.send(bundle, progress=False)
    finally:
        target.close()
    # K93/K94 Recovery can retain the staging upload without entering it.
    # Re-sending only the small matching loader preserves the loaded kernel.
    time.sleep(2)
    candidate = appleusb.find()
    if candidate is not None and appleusb.Device(candidate).mode == "Recovery":
        target = device("Recovery", 5)
        print("Recovery still responsive; sending matching standalone loader", flush=True)
        try:
            target.send((bundle_dir / "linux-boot.bin").read_bytes(), progress=False)
        finally:
            target.close()
    print("Bundle sent; waiting for Linux CDC ACM console", flush=True)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        ports = [p.device for p in list_ports.comports() if (p.vid, p.pid) == (0x0525, 0xA4AA)]
        if len(ports) == 1:
            break
        if len(ports) > 1:
            raise RuntimeError("Ambiguous Linux USB serial devices")
        time.sleep(.3)
    else:
        raise RuntimeError("No Linux USB console appeared; inspect display and watchdog recovery")
    print("Linux USB console appeared", flush=True)
    if args.skip_serial:
        print("Linux USB enumeration verified; ACM left closed for network diagnostics", flush=True)
        return
    with (WORK / "k94-linux-console.log").open("wb") as log, serial.Serial(ports[0], 115200, timeout=.3, write_timeout=5) as console:
        time.sleep(1)
        console.write(b"\necho K94_PROBE_BEGIN; uname -a; cat /proc/device-tree/model; echo; cat /proc/mounts; cat /sys/class/graphics/fb0/virtual_size; cat /sys/class/graphics/fb0/bits_per_pixel; echo K94_PROBE_DONE\n")
        captured = bytearray()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            chunk = console.read(4096)
            if chunk:
                log.write(chunk); log.flush(); captured.extend(chunk)
                if b"\nK94_PROBE_DONE\r\n" in captured and b"Apple iPad 2 GSM" in captured:
                    break
        print(captured.decode(errors="replace"), flush=True)
        if b"Linux" not in captured or b"Apple iPad 2 GSM" not in captured:
            raise RuntimeError("USB console did not establish a K94 Linux userspace boot")
    print("K94 Linux userspace verified over USB; " +
          ("automatic watchdog reset disabled" if args.no_watchdog else "watchdog recovery remains armed"), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError, KeyError, ValueError) as exc:
        raise SystemExit(str(exc))
