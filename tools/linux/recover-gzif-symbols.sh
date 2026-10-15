#!/usr/bin/env bash
# Read-only, offline symbol recovery for the owner's SM-S918N GZIF boot image.
# Does NOT run BOPE, flash partitions or alter the connected Android device.
set -Eeuo pipefail

firmware_dir="${1:-$HOME/rmg-firmware/s918n-gzif}"
boot_lz4="$firmware_dir/boot.img.lz4"
kernel="$firmware_dir/unpacked/kernel"
output="$firmware_dir"
expected_hash="c7f37c99b54a8a164b082a88af5a833f7f48bcd4ca98db9dbd8b4192e984253b"
expected_kernel="5.15.197-android13-8-34343818-abS918NKSU8GZIF"

die() { echo "[ERROR] $*" >&2; exit 1; }
for tool in sha256sum kallsyms-finder vmlinux-to-elf readelf python3; do
  command -v "$tool" >/dev/null || die "$tool not found. Activate the project .venv and install the dependency."
done
[[ -f "$boot_lz4" ]] || die "Missing: $boot_lz4"
[[ -f "$kernel" ]] || die "Missing extracted kernel: $kernel"

actual_hash="$(sha256sum "$boot_lz4" | awk '{print $1}')"
[[ "$actual_hash" == "$expected_hash" ]] || die "Boot LZ4 SHA-256 mismatch. Refusing symbol recovery."

# Verify the exact kernel release independently before any expensive processing.
actual_release="$(python3 - "$kernel" <<'PY'
from pathlib import Path
from sys import argv
from tools.bope.kernel import kernel_identity
print(kernel_identity(Path(argv[1])).release)
PY
)" || die "Unable to determine kernel release"
[[ "$actual_release" == "$expected_kernel" ]] || die "Kernel release mismatch: $actual_release"

echo "[OK] Boot SHA-256 and kernel release both match GZIF"
echo "[INFO] Working directory: $output"
echo "[INFO] Using tool auto-detected base address; do not assume the ZZI8 base is correct"
echo "[INFO] Kernel symbol recovery may take several minutes"

# Recover the native kernel symbols without reusing donor symbol addresses.
kallsyms-finder "$kernel" --output "$output/kallsyms_GZIF.kallsyms" \
  >"$output/kallsyms-finder.log" 2>&1 \
  || die "kallsyms recovery failed. Inspect $output/kallsyms-finder.log"
[[ -s "$output/kallsyms_GZIF.kallsyms" ]] || die "Empty kallsyms output"

# Rebuild a symbolized analysis ELF. This is not a flashable image.
vmlinux-to-elf "$kernel" "$output/vmlinux_GZIF.elf" \
  >"$output/vmlinux-to-elf.log" 2>&1 \
  || die "ELF reconstruction failed. Inspect $output/vmlinux-to-elf.log"
[[ -s "$output/vmlinux_GZIF.elf" ]] || die "Empty ELF output"
readelf -h "$output/vmlinux_GZIF.elf" | grep -Eq 'Machine:.*AArch64' \
  || die "ELF is not AArch64"

echo "[OK] Recovered $(wc -l < "$output/kallsyms_GZIF.kallsyms") symbol table lines"
echo "[OK] Generated: $output/vmlinux_GZIF.elf"
echo "[INFO] File sizes:"
ls -lh "$output/kallsyms_GZIF.kallsyms" "$output/vmlinux_GZIF.elf"
echo "[INFO] These artifacts are for analysis only; no root payload is validated."
