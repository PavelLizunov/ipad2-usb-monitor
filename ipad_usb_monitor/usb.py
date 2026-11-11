#!/usr/bin/env python3
"""Run one command on the K94 Linux USB console."""
import argparse
import fcntl
from pathlib import Path
import shlex
import time
import uuid

import serial
from .paths import STATE
from serial.tools import list_ports


def _run(command, timeout=15):
    marker = "K94_" + uuid.uuid4().hex
    begin = marker + "_BEGIN"
    end = marker + "_END"
    line = ("printf '\\n" + begin + "\\n'; sh -c " + shlex.quote(command) +
            "; result=$?; printf '\\n" + end + " %s\\n' \"$result\"\n")
    ports = [port.device for port in list_ports.comports()
             if (port.vid, port.pid) == (0x0525, 0xA4AA)]
    if len(ports) != 1:
        raise RuntimeError(f"Expected one K94 Linux USB console, found {len(ports)}")
    with serial.Serial(ports[0], 115200, timeout=.2, write_timeout=5) as console:
        console.write(b"\n")
        console.reset_input_buffer()
        console.write(line.encode())
        data = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data.extend(console.read(8192))
            normalized = bytes(data).replace(b"\r", b"")
            start = normalized.find(("\n" + begin + "\n").encode())
            finish = normalized.find(("\n" + end + " ").encode(), max(start, 0))
            if start >= 0 and finish >= 0:
                tail = normalized[finish + len(end) + 2:]
                if b"\n" in tail:
                    return normalized[start + len(begin) + 2:finish].decode(errors="replace"), int(tail.splitlines()[0])
        raise TimeoutError("No completion marker from the K94 USB console")


def run(command, timeout=15):
    lock_path = STATE / "usb-console.lock"
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _run(command, timeout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    if bool(args.command) == bool(args.file):
        parser.error("provide a command or --file")
    output, status = run(args.file.read_text() if args.file else args.command, args.timeout)
    print(output, end="" if output.endswith("\n") else "\n")
    raise SystemExit(status)
