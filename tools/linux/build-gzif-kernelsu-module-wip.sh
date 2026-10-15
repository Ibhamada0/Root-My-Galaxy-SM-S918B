#!/usr/bin/env bash
# Source-build a GZIF KernelSU Next v3.4.0 LKM against an EXACT prepared
# SM-S918N/GZIF Kbuild tree. Host only: no adb, insmod, signing or flashing.
set -euo pipefail

expected="5.15.197-android13-8-34343818-abS918NKSU8GZIF"
expected_commit="1a879d6a866f80b1fa1c1009a2ffa747873cbb5e"
source_dir="${GZIF_KSU_SOURCE_ROOT:-$HOME/rmg-firmware/gzif-kernelsu-source}/KernelSU-Next-v3.4.0"

if [[ $# -ne 1 ]]; then
  echo "Usage: bash tools/linux/build-gzif-kernelsu-module-wip.sh /absolute/path/to/prepared-GZIF-KDIR" >&2
  echo "KDIR must have exact kernel.release, matching .config/Module.symvers, generated headers and modpost." >&2
  exit 2
fi

kdir="$(realpath -e -- "$1")"
if [[ ! -d "$kdir" ]]; then
  echo "[ERROR] KDIR does not exist: $kdir" >&2
  exit 2
fi

check_file() {
  if [[ ! -s "$kdir/$1" ]]; then
    echo "[ERROR] Missing/empty prepared GZIF Kbuild artifact: $kdir/$1" >&2
    exit 2
  fi
}

check_file Makefile
check_file .config
check_file include/config/auto.conf
check_file include/config/kernel.release
check_file include/generated/utsrelease.h
check_file Module.symvers
check_file scripts/mod/modpost
check_file vmlinux

got_release="$(cat -- "$kdir/include/config/kernel.release")"
if [[ "$got_release" != "$expected" ]]; then
  echo "[ERROR] KDIR release mismatch: got=$got_release expected=$expected" >&2
  exit 2
fi
if ! grep -Fqx "#define UTS_RELEASE \"$expected\"" "$kdir/include/generated/utsrelease.h"; then
  echo "[ERROR] generated UTS_RELEASE does not match exact GZIF" >&2
  exit 2
fi
for config in CONFIG_MODULES=y CONFIG_MODVERSIONS=y CONFIG_MODULE_SIG=y CONFIG_MODULE_SIG_PROTECT=y; do
  if ! grep -Fqx "$config" "$kdir/.config"; then
    echo "[ERROR] Exact GZIF module policy is not present: $config" >&2
    exit 2
  fi
done
if ! grep -Fqx "CONFIG_MODULES=y" "$kdir/include/config/auto.conf"; then
  echo "[ERROR] Kernel auto.conf was not prepared with modules enabled" >&2
  exit 2
fi

if [[ ! -d "$source_dir/.git" ]]; then
  echo "[ERROR] KernelSU v3.4.0 source missing: $source_dir" >&2
  echo "Run bash tools/linux/prepare-gzif-kernelsu-source.sh" >&2
  exit 2
fi
got_commit="$(git -C "$source_dir" rev-parse HEAD)"
if [[ "$got_commit" != "$expected_commit" ]]; then
  echo "[ERROR] KernelSU source differs from pinned v3.4.0: $got_commit" >&2
  exit 2
fi
if [[ -n "$(git -C "$source_dir" status --porcelain)" ]]; then
  echo "[ERROR] KernelSU source tree is modified; use the pristine clone" >&2
  exit 2
fi

for tool in git make clang llvm-readelf modinfo sha256sum python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "[ERROR] Host tool missing: $tool" >&2
    exit 2
  fi
done
if [[ ! -x "$kdir/scripts/mod/modpost" ]]; then
  echo "[ERROR] Kernel modpost must be executable (full prepared Kbuild tree)" >&2
  exit 2
fi
if [[ "$(llvm-readelf -h "$kdir/vmlinux" 2>/dev/null | grep -c 'Machine:.*AArch64' || true)" -ne 1 ]]; then
  echo "[ERROR] Matched KDIR vmlinux must be ELF AArch64" >&2
  exit 2
fi

jobs="${GZIF_KSU_JOBS:-4}"
if [[ ! "$jobs" =~ ^[1-9][0-9]*$ || "$jobs" -gt 16 ]]; then
  echo "[ERROR] GZIF_KSU_JOBS must be 1..16" >&2
  exit 2
fi
outroot="$HOME/rmg-firmware/gzif-kernelsu-builds"
mkdir -p -- "$outroot"
workspace="$(mktemp -d "$outroot/gzif-ksu-source-XXXXXXXX")"
mkdir -p "$workspace/source"
cp -a -- "$source_dir/." "$workspace/source/"
moddir="$workspace/source/kernel"
log="$workspace/kbuild.log"

echo "[BUILD] KernelSU Next $expected_commit against exact-release KDIR"
echo "KDIR: $kdir"
echo "Workspace: $workspace"
echo "Executing: make -C KDIR M=WORKSPACE/kernel CONFIG_KSU=m LLVM=1 ARCH=arm64 modules"
if ! make -C "$kdir" M="$moddir" src="$moddir" CONFIG_KSU=m LLVM=1 ARCH=arm64 -j"$jobs" modules >"$log" 2>&1; then
  echo "[ERROR] Kbuild failed; full log: $log" >&2
  tail -n 45 "$log" >&2
  exit 2
fi

ko="$moddir/kernelsu.ko"
if [[ ! -s "$ko" ]]; then
  echo "[ERROR] No kernelsu.ko produced; inspect $log" >&2
  exit 2
fi
if ! llvm-readelf -h "$ko" | grep -q 'Machine:.*AArch64'; then
  echo "[ERROR] KernelSU output architecture is not AArch64" >&2
  exit 2
fi
vermagic="$(modinfo -F vermagic "$ko")"
if [[ "$vermagic" != "$expected "* ]]; then
  echo "[ERROR] Built KernelSU vermagic mismatch: $vermagic" >&2
  exit 2
fi

report="$workspace/build-report.json"
python3 - "$report" "$ko" "$kdir" "$expected_commit" "$log" <<'PY'
from pathlib import Path
import hashlib
import json
import sys

report, ko, kdir, commit, log = (
    Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]),
    sys.argv[4], Path(sys.argv[5])
)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
data = {
    "status": "HOST_SOURCE_BUILT_GZIF_KSU_WIP_NOT_DEVICE_VALIDATED",
    "device": "SM-S918N",
    "firmware": "S918NKSU8GZIF",
    "source_commit": commit,
    "kernel_build_directory": str(kdir),
    "kernel_config_sha256": sha(kdir / ".config"),
    "kernel_module_symvers_sha256": sha(kdir / "Module.symvers"),
    "kernel_vmlinux_sha256": sha(kdir / "vmlinux"),
    "module": str(ko),
    "module_sha256": sha(ko),
    "module_size": ko.stat().st_size,
    "kbuild_log": str(log),
    "limitations": [
        "KDIR release match cannot prove exact Samsung binary/config provenance.",
        "No module signing/admission check against Samsung protected-symbol policy.",
        "No device operation, no insmod and no KernelSU control handshake.",
        "No ksud embedding and no BOPE runtime validation.",
        "DO NOT DEPLOY, LOAD OR FLASH this candidate."
    ]
}
report.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
PY

echo "[BUILT] kernelsu.ko: ELF64/AArch64; $vermagic"
sha256sum "$ko"
echo "Report: $report"
echo "Status: HOST_SOURCE_BUILT_GZIF_KSU_WIP_NOT_DEVICE_VALIDATED"
echo "DO NOT DEPLOY, LOAD OR FLASH this WIP module."
