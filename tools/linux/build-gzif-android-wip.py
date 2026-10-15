#!/usr/bin/env python3
"""Compile the already generated GZIF BOPE engine in an isolated WSL workspace.

Host-only compilation. Does NOT execute or install compiled Android binaries,
modify a phone, retarget/sign a kernel module, or register an app target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
EXPECTED = {
    "TARGET_MODEL": "SM-S918N",
    "TARGET_DEVICE": "dm3q",
    "TARGET_BUILD": "S918NKSU8GZIF",
    "TARGET_KERNEL_RELEASE": "5.15.197-android13-8-34343818-abS918NKSU8GZIF",
    "TARGET_FINGERPRINT": (
        "samsung/dm3qksx/dm3q:17/CP2A.260605.016/"
        "S918NKSU8GZIF:user/release-keys"
    ),
}
STATUS = "HOST_BUILD_ONLY_NOT_DEVICE_VALIDATED"


def parse_header_string_macro(header: str, name: str) -> str:
    """Read one exact quoted C identity macro, single- or two-line form."""
    pattern = re.compile(
        rf'^[ \t]*#define[ \t]+{re.escape(name)}'
        r'(?:[ \t]+\\\r?\n[ \t]*|[ \t]+)'
        r'"([^"\r\n]*)"[ \t]*\r?$',
        re.MULTILINE,
    )
    matches = pattern.findall(header)
    if len(matches) != 1:
        raise ValueError(
            f"Generated target.h must contain exactly one string macro {name}; "
            f"found {len(matches)}"
        )
    return matches[0]


def validate_inputs(target: Path) -> tuple[Path, Path]:
    """Fail closed before copying/compiling if generated target is wrong."""
    manifest = json.loads((target / "port-manifest.json").read_text())
    if manifest.get("status") != "GENERATED_WIP_DEVICE_VALIDATION_REQUIRED":
        raise ValueError("GZIF target is not in the expected unvalidated WIP state")
    if manifest.get("target", {}).get("build") != EXPECTED["TARGET_BUILD"]:
        raise ValueError("Manifest firmware build mismatch")
    if manifest.get("target", {}).get("kernel_release") != EXPECTED["TARGET_KERNEL_RELEASE"]:
        raise ValueError("Manifest kernel release mismatch")
    if manifest.get("contract", {}).get("verification", {}).get("passed") is not True:
        raise ValueError("GZIF ELF/BTF contract checks did not pass")
    engine = target / "brazilian-open-payload-engine"
    header = (engine / "src/target.h").read_text()
    for macro, expected in EXPECTED.items():
        actual = parse_header_string_macro(header, macro)
        if actual != expected:
            raise ValueError(
                f"Generated target.h does not match {macro}: "
                f"expected {expected!r}, got {actual!r}"
            )
    helper = target / "helper"
    for required in (
        engine / "Makefile", engine / "src/00_orchestrator.c",
        helper / "Makefile", helper / "su_daemon.c",
        REPO / "native/compact_log.c",
        REPO / "native/compact_log.h",
        REPO / "stability-launcher/bope-stability-launcher.c",
    ):
        if not required.is_file():
            raise FileNotFoundError(f"Missing build input: {required}")
    return engine, helper


def check_ndk(value: str | None) -> Path:
    ndk = Path(value).expanduser() if value else (
        Path.home() / "Android/Sdk/ndk/28.2.13676358"
    )
    ndk = ndk.resolve()
    compiler = (
        ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin/"
        "aarch64-linux-android35-clang"
    )
    if not compiler.is_file() or not os.access(compiler, os.X_OK):
        raise FileNotFoundError(
            "Android NDK 28.x AArch64 API-35 compiler missing: "
            f"{compiler}\nInstall the matching NDK in WSL, or pass --ndk "
            "/path/to/android-ndk. No build has started."
        )
    return ndk


def run_build(command: list[str], cwd: Path, logfile: Path, env: dict) -> None:
    print(f"Building in: {cwd}")
    print("Command:", " ".join(command))
    with logfile.open("w") as stream:
        result = subprocess.run(
            command, cwd=cwd, env=env, stdout=stream,
            stderr=subprocess.STDOUT, check=False,
        )
    if result.returncode:
        tail = logfile.read_text(errors="replace").splitlines()[-45:]
        print("\n".join(tail), file=sys.stderr)
        raise RuntimeError(
            f"Build command failed with exit {result.returncode}; log: {logfile}"
        )


def elf_aarch64(path: Path) -> bool:
    probe = subprocess.run(
        ["readelf", "-h", str(path)], capture_output=True, text=True,
        check=False,
    )
    return (
        probe.returncode == 0
        and "ELF64" in probe.stdout
        and "AArch64" in probe.stdout
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndk", help="Path to installed Linux Android NDK")
    parser.add_argument(
        "--target", type=Path, default=(
            Path.home() / "rmg-firmware/gzif-contracts/s918ngzif-WIP"
        ),
    )
    parser.add_argument(
        "--controlled-one-shot", action="store_true",
        help="generate isolated WIP source with GZIF one-shot safety overlay",
    )
    args = parser.parse_args()
    workspace: Path | None = None
    try:
        engine, helper = validate_inputs(args.target.expanduser())
        ndk = check_ndk(args.ndk or os.environ.get("ANDROID_NDK_HOME"))
        if shutil.which("make") is None or shutil.which("readelf") is None:
            raise FileNotFoundError("Install host build dependencies: make, binutils")
        outroot = Path.home() / "rmg-firmware/gzif-android-builds"
        outroot.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix="s918ngzif-", dir=outroot))
        stage = workspace / "targets/s918ngzif-WIP"
        stage.mkdir(parents=True)
        staged_engine = stage / "brazilian-open-payload-engine"
        staged_helper = stage / "helper"
        shutil.copytree(engine, staged_engine, ignore=shutil.ignore_patterns(
            "build", "__pycache__", "evidence"
        ))
        shutil.copytree(helper, staged_helper, ignore=shutil.ignore_patterns(
            "build", "__pycache__"
        ))
        # Generated Makefile's ../../../native and ../../../stability-launcher
        # resolve to workspace/native and workspace/stability-launcher.
        shutil.copytree(REPO / "native", workspace / "native",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO / "stability-launcher",
                        workspace / "stability-launcher",
                        ignore=shutil.ignore_patterns("__pycache__"))
        logdir = workspace / "logs"
        logdir.mkdir()
        overlay_report = None
        if args.controlled_one_shot:
            from gzif_controlled_trial_overlay import apply_overlay
            overlay_report = apply_overlay(staged_engine)
            (workspace / "one-shot-overlay.json").write_text(
                json.dumps(overlay_report, indent=2, sort_keys=True) + "\n"
            )
            print("[ONE-SHOT] Prepared GZIF-only guarded source copy")
        env = os.environ.copy()
        env["ANDROID_NDK_HOME"] = str(ndk)
        run_build(
            ["make", "clean", "so", "test-aar-read-plan",
             "test-fops-layout", "test-compact-log"],
            staged_engine, logdir / "bope-build.log", env,
        )
        run_build(
            ["make", "clean", "all"],
            staged_helper, logdir / "helper-build.log", env,
        )
        generated = {
            "payload_so": staged_engine / "build/payload.so",
            "mm_exec_factory": staged_engine / "build/mm-exec-factory",
            "stability_launcher": (
                staged_engine / "build/stability-launcher-s918ngzif"
            ),
            "root_helper": staged_helper / "build/cve-2026-43499-root",
        }
        artifacts = {}
        for name, path in generated.items():
            if not path.is_file() or not elf_aarch64(path):
                raise ValueError(f"Built artifact is not ELF64/AArch64: {name}: {path}")
            artifacts[name] = {
                "path": str(path),
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "architecture": "ELF64/AArch64",
            }
        report = {
            "status": (
                "HOST_BUILD_ONE_SHOT_EXPERIMENTAL_NOT_DEVICE_VALIDATED"
                if args.controlled_one_shot else STATUS
            ),
            "one_shot_overlay": overlay_report,
            "firmware": EXPECTED["TARGET_BUILD"],
            "kernel_release": EXPECTED["TARGET_KERNEL_RELEASE"],
            "ndk": str(ndk),
            "artifacts": artifacts,
            "limitations": [
                "Compilation and host regressions only: no Android device run",
                "No BOPE exploit or KernelSU operation validated",
                "Donor-inherited calibration still unverified",
                "No insmod, flashing, ADB, app integration, or install",
            ],
        }
        report_path = workspace / "build-report.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        for name, item in artifacts.items():
            print(f"[BUILT] {name}: ELF64/AArch64 ({item['size']} bytes)")
        print("Report:", report_path)
        print("Status: " + report["status"])
        print("DO NOT DEPLOY these WIP binaries to Android.")
        if args.controlled_one_shot:
            print("One-shot overlay is NOT a safety certification.")
        return 0
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        if workspace is not None:
            print(f"Build workspace and logs retained: {workspace}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
