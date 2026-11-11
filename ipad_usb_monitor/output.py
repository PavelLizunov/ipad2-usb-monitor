#!/usr/bin/env python3
"""Create and configure the dedicated Hyprland output without changing others."""
import json
import os
import socket
import subprocess
import time
from .settings import load


def hypr(*args):
    return subprocess.check_output(["hyprctl", *args], text=True)


def main():
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        instances = json.loads(hypr("instances", "-j"))
        if len(instances) != 1:
            raise RuntimeError("Could not identify a unique running Hyprland session")
        os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = instances[0]["instance"]
    for attempt in range(60):
        with socket.socket() as probe:
            try:
                probe.bind(("10.94.0.1", 0))
                break
            except OSError:
                if attempt == 59:
                    raise RuntimeError("Waiting for the iPad USB Ethernet address 10.94.0.1")
                time.sleep(1)
    monitors = json.loads(hypr("monitors", "all", "-j"))
    if not any(m["name"] == "IPAD2" for m in monitors):
        print(hypr("output", "create", "headless", "IPAD2"), end="")
    others = [m for m in monitors if m["name"] != "IPAD2" and not m.get("disabled")]
    right = round(max((m["x"] + m["width"] / m["scale"] for m in others), default=0))
    settings = load()
    width, height = settings["width"], settings["height"]
    if settings["rotation"] % 2:
        width, height = height, width
    print(hypr("eval", 'hl.monitor({output="IPAD2", mode="' + str(width) + 'x' + str(height) +
               '@60", position="' + str(right) + 'x0", scale=1, transform=0})'), end="")


if __name__ == "__main__":
    main()
