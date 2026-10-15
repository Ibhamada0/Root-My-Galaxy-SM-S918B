#!/usr/bin/env python3
"""Build a GZIF-specific KernelSU Next ksud loader, HOST ONLY.

Embeds the *previously statically audited* ZZI8-derived, GZIF-vermagic
metadata-only candidate into a disposable copy of upstream v3.4.0 ksud.
This does NOT validate module admission and NEVER connects to Android.
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

ROOT = Path(__file__).resolve().parents[2]
TARGET = Path.home() / "rmg-firmware/gzif-contracts/s918ngzif-WIP"
SOURCE = (
    Path(os.environ.get("GZIF_KSU_SOURCE_ROOT",
                        str(Path.home() / "rmg-firmware/gzif-kernelsu-source")))
    / "KernelSU-Next-v3.4.0"
)
NDK = Path(os.environ.get(
    "ANDROID_NDK_HOME",
    str(Path.home() / "Android/Sdk/ndk/28.2.13676358"),
)).expanduser()
BUILD_ROOT = Path.home() / "rmg-firmware/gzif-kernelsu-loader-builds"
RELEASE = "5.15.197-android13-8-34343818-abS918NKSU8GZIF"
DONOR_RELEASE = "5.15.197-android13-8-34343818-abS918BXXUAZZI8"
COMMIT = "1a879d6a866f80b1fa1c1009a2ffa747873cbb5e"
DONOR_SHA256 = "eb518dd33f782fa4e47f58e16a7148029b96eaff98974e10067b409f9b5ff090"
DONOR = (ROOT / "targets/zzi8-WIP/kernelsu-next/out"
         / "kernelsu-next-zzi8-v3.4.0/android13-5.15_kernelsu.ko")
CANDIDATE = TARGET / "analysis-only/kernelsu-gzif-vermagic-WIP.ko"
AUDIT = TARGET / "analysis-only/kernelsu-gzif-metadata-static-audit.json"
HELPER = ROOT / "targets/zzi8-WIP/helper/su_daemon.c"
KMI_ASSET = "android13-5.15_kernelsu.ko"


def fail(message: str) -> None:
    raise ValueError(message)


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def execute(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, check=True, **kwargs)


def check_inputs() -> tuple[bytes, Path]:
    for label, path in [
        ("KernelSU upstream v3.4.0", SOURCE),
        ("original ZZI8 donor module", DONOR),
        ("previously audited GZIF metadata-only module", CANDIDATE),
        ("host-only static audit report", AUDIT),
        ("target root helper", HELPER),
    ]:
        if not path.exists():
            fail(f"Missing {label}: {path}")

    if not (SOURCE / "userspace/ksud/Cargo.lock").is_file():
        fail(f"Source is incomplete: {SOURCE}")
    if not (SOURCE / "userspace/ksud/src/late_load.rs").is_file():
        fail("Upstream v3.4.0 has no late_load.rs")
    actual_commit = execute(["git", "-C", str(SOURCE), "rev-parse", "HEAD"],
                            capture_output=True).stdout.strip()
    if actual_commit != COMMIT:
        fail(f"Wrong KernelSU Next source commit: {actual_commit}")
    dirty = execute(["git", "-C", str(SOURCE), "status", "--porcelain"],
                    capture_output=True).stdout.strip()
    if dirty:
        fail("Upstream KernelSU source checkout has uncommitted changes")

    audit = json.loads(AUDIT.read_text())
    if (audit.get("passed") is not True
            or audit.get("target_release") != RELEASE
            or audit.get("evaluation") != "METADATA_ONLY_LOCAL_WIP_CANDIDATE"
            or audit.get("status") != "NOT_DEVICE_VALIDATED_NOT_APPROVED_TO_LOAD"):
        fail("Existing donor-module static audit was not an exact GZIF pass")

    donor = DONOR.read_bytes()
    if sha256(donor) != DONOR_SHA256:
        fail("Donor module SHA-256 mismatch; not the inspected developer copy")
    old = ("vermagic=" + DONOR_RELEASE).encode("ascii")
    new = ("vermagic=" + RELEASE).encode("ascii")
    if len(old) != len(new) or donor.count(old) != 1:
        fail("Donor vermagic cannot be replaced unambiguously")
    expected = donor.replace(old, new, 1)
    actual = CANDIDATE.read_bytes()
    if actual != expected:
        fail("Candidate is not the EXACT one-field vermagic-only donor copy")
    if audit.get("donor_sha256") != DONOR_SHA256:
        fail("Static audit did not refer to the pinned donor module")

    helper = HELPER.read_text()
    if ('"android13-5.15"' not in helper or
            '"com.rifsxd.ksunext"' not in helper or
            'KSU_LOADER_PATH "/data/local/tmp/ksud-selected"' not in helper):
        fail("Root helper no longer agrees with KernelSU KMI/package/loader path")

    if not shutil.which("cargo") or not shutil.which("rustc"):
        fail("Rust cargo and rustc required in WSL to build the actual ksud binary")
    if not shutil.which("readelf"):
        fail("readelf required for ELF verification")
    host = NDK / "toolchains/llvm/prebuilt/linux-x86_64"
    linker = host / "bin/aarch64-linux-android35-clang"
    if not linker.is_file():
        fail(f"Missing Android NDK API-35 compiler: {linker}")
    return actual, host


def main() -> int:
    workspace: Path | None = None
    try:
        module_bytes, host = check_inputs()
        BUILD_ROOT.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix="s918ngzif-ksud-", dir=BUILD_ROOT))
        staged = workspace / "KernelSU-Next-v3.4.0"
        shutil.copytree(SOURCE, staged)
        asset = staged / "userspace/ksud/bin/aarch64" / KMI_ASSET
        if asset.exists():
            fail(f"Unexpected embedded module already in upstream: {asset}")
        asset.write_bytes(module_bytes)

        # RustEmbed reads the module during compilation from this exact path.
        cargo_manifest = staged / "userspace/ksud/Cargo.toml"
        cargo_target = workspace / "cargo-target"
        linker = host / "bin/aarch64-linux-android35-clang"
        sysroot = host / "sysroot"
        env = os.environ.copy()
        env.update({
            "ANDROID_NDK_HOME": str(NDK),
            "ANDROID_NDK_ROOT": str(NDK),
            "CARGO_TARGET_DIR": str(cargo_target),
            "CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER": str(linker),
            "CC_aarch64_linux_android": str(linker),
            "AR_aarch64_linux_android": str(host / "bin/llvm-ar"),
            "KSU_LKM_BOOTSTRAP_CC": str(host / "bin/clang"),
            "BINDGEN_EXTRA_CLANG_ARGS_aarch64_linux_android":
                f"--sysroot={sysroot} -I{sysroot}/usr/include/aarch64-linux-android",
        })
        log_path = workspace / "ksud-cargo-build.log"
        cmd = [
            "cargo", "build", "--locked", "--release", "--target",
            "aarch64-linux-android", "--manifest-path", str(cargo_manifest),
        ]
        print(f"[SOURCE] KernelSU Next v3.4.0 pinned: {COMMIT}", flush=True)
        print("[MODULE] EXACT metadata-only donor candidate staged as embedded "
              + KMI_ASSET, flush=True)
        print("[BUILD] Actual Android ksud via cargo; no ADB/insmod/flash",
              flush=True)
        print(f"[LOG] {log_path}", flush=True)
        with log_path.open("w") as log_file:
            result = subprocess.run(cmd, env=env, cwd=staged, stdout=log_file,
                                    stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            tail = log_path.read_text(errors="replace").splitlines()[-35:]
            print("\n".join(tail), file=sys.stderr)
            fail(f"Cargo failed with {result.returncode}; full log: {log_path}")

        built = cargo_target / "aarch64-linux-android/release/ksud"
        if not built.is_file():
            fail(f"Cargo reported success but ksud is missing: {built}")
        elf = execute(["readelf", "-h", str(built)], capture_output=True).stdout
        if ("ELF64" not in elf or "AArch64" not in elf):
            fail("ksud does not have expected 64-bit AArch64 ELF format")
        loader = workspace / "ksud-selected.WIP"
        shutil.copy2(built, loader)
        loader.chmod(0o700)

        report = {
            "status": "HOST_BUILT_KSUD_WITH_ZZI8_DONOR_METADATA_GZIF_WIP_NOT_DEVICE_VALIDATED",
            "firmware": "S918NKSU8GZIF",
            "kernel_release": RELEASE,
            "source_commit": COMMIT,
            "module_source": "ZZI8 v3.4.0 donor; exact vermagic-only GZIF copy",
            "module_sha256": sha256(module_bytes),
            "embedded_asset": KMI_ASSET,
            "loader_path": str(loader),
            "loader_sha256": sha256(loader.read_bytes()),
            "loader_bytes": loader.stat().st_size,
            "rust_build_log": str(log_path),
            "limitations": [
                "This is NOT a source-rebuilt GZIF kernelsu.ko",
                "Static compatibility is NOT proof of Samsung module-load admission",
                "KernelSU control handshake, SELinux restoration and persistence unverified",
                "BOPE kernel mutation and temporary root NOT validated",
                "DO NOT DEPLOY, LOAD, FLASH or invoke this WIP loader on device",
            ],
        }
        out = workspace / "build-report.json"
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"[BUILT] ksud-selected.WIP: ELF64/AArch64 ({loader.stat().st_size} bytes)")
        print(f"Report: {out}")
        print("Status: HOST BUILT; device module admission NOT validated")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, KeyError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        if workspace:
            print(f"Build directory retained: {workspace}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
