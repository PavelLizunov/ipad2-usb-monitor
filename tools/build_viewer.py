#!/usr/bin/env python3
"""Build a pinned static ARMv7 viewer; all downloads stay in .build."""
import hashlib
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / ".build"
PINS = {
    "fbvnc": ("https://github.com/aligrudi/fbvnc.git", "1fcf012a807cdbcd6db0d1ddd4f58f49fcaf5c6b"),
    "libjpeg-turbo": ("https://github.com/libjpeg-turbo/libjpeg-turbo.git", "4e151a4ad91001b3aa8c2ece2205c15f487ce320"),
    "zlib-ng": ("https://github.com/zlib-ng/zlib-ng.git", "860e4cff7917d93f54f5d7f0bc1d0e8b1a3cb988"),
}
ZIG_VERSION = "0.17.1"
ZIG_SHA256 = "3581863e3cbcfd0fce0efc682ce7e9e93da96668a977791d356a26d2a7e9b17a"


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def main():
    BUILD.mkdir(exist_ok=True)
    for name, (url, commit) in PINS.items():
        source = BUILD / name
        if not source.exists():
            run("git", "init", source)
            run("git", "-C", source, "remote", "add", "origin", url)
            run("git", "-C", source, "fetch", "--depth=1", "origin", commit)
            run("git", "-C", source, "checkout", "--detach", "FETCH_HEAD")
        actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if actual != commit:
            raise RuntimeError("Unexpected dependency revision: " + name)
    patch = ROOT / "patches/fbvnc-monitor.patch"
    source = BUILD / "fbvnc"
    forward = subprocess.run(["git", "-C", str(source), "apply", "--check", str(patch)], capture_output=True)
    if forward.returncode == 0:
        run("git", "-C", source, "apply", patch)
    else:
        run("git", "-C", source, "apply", "--reverse", "--check", patch)
    zig_dir = BUILD / ("zig-x86_64-linux-" + ZIG_VERSION)
    if not zig_dir.exists():
        archive = BUILD / (zig_dir.name + ".tar.xz")
        with urllib.request.urlopen("https://ziglang.org/download/" + ZIG_VERSION + "/" + archive.name, timeout=30) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        with archive.open("rb") as data:
            if hashlib.file_digest(data, "sha256").hexdigest() != ZIG_SHA256:
                raise RuntimeError("Official Zig archive SHA256 mismatch")
        with tarfile.open(archive) as files:
            files.extractall(BUILD, filter="data")
    zig = zig_dir / "zig"
    compiler = BUILD / "arm-cc"
    compiler.write_text("#!/bin/sh\nexec " + shlex.quote(str(zig)) + " cc -target arm-linux-musleabihf -mcpu=cortex_a9 \"$@\"\n")
    compiler.chmod(0o755)
    ar = shutil.which("llvm-ar") or shutil.which("ar")
    ranlib = shutil.which("llvm-ranlib") or shutil.which("ranlib")
    if not ar or not ranlib:
        raise RuntimeError("Install binutils (ar/ranlib) or LLVM archive tools")
    common = ["-DCMAKE_SYSTEM_NAME=Linux", "-DCMAKE_SYSTEM_PROCESSOR=arm", "-DCMAKE_C_COMPILER=" + str(compiler),
              "-DCMAKE_AR=" + ar, "-DCMAKE_RANLIB=" + ranlib, "-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY", "-DCMAKE_BUILD_TYPE=Release"]
    run("cmake", "-S", BUILD / "libjpeg-turbo", "-B", BUILD / "jpeg-arm", *common,
        "-DENABLE_SHARED=OFF", "-DENABLE_STATIC=ON", "-DWITH_SIMD=ON", "-DREQUIRE_SIMD=ON", "-DWITH_TURBOJPEG=ON", "-DWITH_TOOLS=OFF", "-DWITH_TESTS=OFF")
    run("cmake", "--build", BUILD / "jpeg-arm", "--target", "turbojpeg-static", "-j", "4")
    run("cmake", "-S", BUILD / "zlib-ng", "-B", BUILD / "zlib-ng-arm", *common,
        "-DBUILD_SHARED_LIBS=OFF", "-DZLIB_COMPAT=ON", "-DZLIB_ENABLE_TESTS=OFF", "-DWITH_GTEST=OFF", "-DWITH_BENCHMARKS=OFF", "-DWITH_NEON=ON")
    run("cmake", "--build", BUILD / "zlib-ng-arm", "-j", "4")
    run(zig, "cc", "-target", "arm-linux-musleabihf", "-mcpu=cortex_a9", "-static", "-s", "-O3",
        "-I", BUILD / "zlib-ng-arm", "-I", BUILD / "zlib-ng", "-I", BUILD / "libjpeg-turbo/src", "-I", BUILD / "jpeg-arm",
        BUILD / "fbvnc/fbvnc.c", BUILD / "fbvnc/draw.c", BUILD / "zlib-ng-arm/libz.a", BUILD / "jpeg-arm/libturbojpeg.a", "-lm", "-o", BUILD / "fbvnc-arm")
    print("Built", BUILD / "fbvnc-arm")


if __name__ == "__main__":
    main()
