#!/usr/bin/env python3
"""Rebuild ONLY the GZIF temporary-root helper with an SELinux expiry fuse.

This does not rebuild BOPE or KernelSU Next or rerun device/host tests.
The source and output are staged in a new host-only work directory;
nothing is installed, loaded or run on Android.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from gzif_root_helper_guard import apply_helper_overlay

HOME = Path.home()
BASE_REPORT = (
    HOME / "rmg-firmware/gzif-android-builds/s918ngzif-7cjfl28m/build-report.json"
)
OUTPUT_ROOT = HOME / "rmg-firmware/gzif-helper-fuse-builds"
EXPECTED = "5.15.197-android13-8-34343818-abS918NKSU8GZIF"
FIRMWARE = "S918NKSU8GZIF"
BIN = "cve-2026-43499-root"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    workspace: Path | None = None
    try:
        require(BASE_REPORT.is_file(), f"Missing verified BOPE report: {BASE_REPORT}")
        report = json.loads(BASE_REPORT.read_text())
        require(
            report.get("status") == "HOST_BUILD_ONE_SHOT_EXPERIMENTAL_NOT_DEVICE_VALIDATED"
            and report.get("firmware") == FIRMWARE
            and report.get("kernel_release") == EXPECTED,
            "Existing BOPE native report does not match the guarded GZIF build",
        )
        baseline = report.get("artifacts", {}).get("root_helper", {})
        require(isinstance(baseline, dict), "Missing original root helper metadata")
        original_binary = Path(str(baseline.get("path", "")))
        require(
            original_binary.name == BIN and original_binary.is_file()
            and sha(original_binary) == baseline.get("sha256")
            and original_binary.stat().st_size == baseline.get("size"),
            "Original helper binary does not match its successful BOPE build report",
        )
        helper_src = original_binary.parent.parent
        require(
            helper_src.is_relative_to(BASE_REPORT.parent)
            and (helper_src / "su_daemon.c").is_file()
            and (helper_src / "Makefile").is_file(),
            f"Expected helper source within original build workspace: {helper_src}",
        )
        ndk = Path(str(report.get("ndk", "")))
        compiler = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android35-clang"
        require(compiler.is_file(), f"Android NDK compiler unavailable: {compiler}")
        require(shutil.which("make") is not None, "GNU make is required")

        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix="s918ngzif-helper-fuse-", dir=OUTPUT_ROOT))
        staged = workspace / "helper"
        shutil.copytree(helper_src, staged, ignore=shutil.ignore_patterns("build"))
        guarded_source_report = apply_helper_overlay(staged)
        (workspace / "helper-source-overlay.json").write_text(
            json.dumps(guarded_source_report, indent=2, sort_keys=True) + "\n"
        )
        log = workspace / "helper-build.log"
        env = os.environ.copy()
        env["ANDROID_NDK_HOME"] = str(ndk)
        print("[SOURCE] Copied previous GZIF helper to isolated host workspace", flush=True)
        print("[GZIF] 180-second independent SELinux restoration fuse + socket expiry", flush=True)
        print("[BUILD] Recompiling ONLY root helper (no BOPE/KSU/test reruns)", flush=True)
        with log.open("w") as stream:
            build = subprocess.run(
                ["make", "clean", "all"], cwd=staged, env=env,
                stdout=stream, stderr=subprocess.STDOUT, check=False,
            )
        if build.returncode != 0:
            print("\n".join(log.read_text(errors="replace").splitlines()[-40:]),
                  file=sys.stderr)
            require(False, f"Root helper compiler error; see {log}")
        target = staged / "build" / BIN
        require(target.is_file(), f"Compiled guarded helper missing: {target}")
        with target.open("rb") as stream:
            magic = stream.read(20)
        require(
            len(magic) == 20 and magic[:4] == b"\x7fELF"
            and magic[4] == 2 and magic[5] == 1
            and int.from_bytes(magic[18:20], "little") == 183,
            "Guarded root helper is not ELF64 little-endian AArch64",
        )
        # Basic linkage contract from final compiled bytes.
        binary = target.read_bytes()
        for marker in (
            b"gzif-selinux-fuse", b"daemon-expired enforcing=",
            b"watchdog enforcing=", b"/data/local/tmp/ksud-selected",
            b"android13-5.15", b"com.rifsxd.ksunext",
        ):
            require(marker in binary, f"Compiled helper lacks marker: {marker!r}")
        output = {
            "status": "GZIF_TEMP_ROOT_HELPER_FUSE_HOST_BUILT_NOT_DEVICE_VALIDATED",
            "firmware": FIRMWARE,
            "kernel_release": EXPECTED,
            "baseline_bope_report": str(BASE_REPORT),
            "baseline_helper_sha256": baseline["sha256"],
            "binary": str(target),
            "sha256": sha(target),
            "size": target.stat().st_size,
            "guard_source_sha256": sha(staged / "su_daemon.c"),
            "guard": guarded_source_report,
            "build_log": str(log),
            "root_ready": False,
            "deployable": False,
            "limitations": [
                "Best-effort SELinux userland recovery, NOT kernel panic recovery",
                "A watchdog cannot restore SELinux if UMH fails before watchdog start",
                "No runtime testing, BOPE kernel mutation or KernelSU module admission",
                "Do not run the experimental root chain on a device",
            ],
        }
        (workspace / "build-report.json").write_text(
            json.dumps(output, indent=2, sort_keys=True) + "\n"
        )
        print(f"[BUILT] guarded root_helper: ELF64/AArch64 ({target.stat().st_size} bytes)")
        print(f"Report: {workspace / 'build-report.json'}")
        print("Status: HOST_BUILT_FUSE_ONLY; root and device load NOT validated")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        if workspace is not None:
            print(f"Build workspace retained: {workspace}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
