#!/usr/bin/env python3
"""Read-only KernelSU Next donor compatibility audit against local GZIF artifacts.

Does not patch vermagic, build modules, run adb, insmod, su, or modify a phone.
Expected outcome for the original ZZI8 donor is passed=false (vermagic mismatch).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.bope.common import executable  # noqa: E402
from tools.bope.errors import BopeError  # noqa: E402
from tools.bope.kernelsu import audit_module  # noqa: E402


RELEASE = "5.15.197-android13-8-34343818-abS918NKSU8GZIF"
DONOR_SHA256 = "eb518dd33f782fa4e47f58e16a7148029b96eaff98974e10067b409f9b5ff090"


def main() -> int:
    project = Path(__file__).resolve().parents[2]
    donor = project / "targets/zzi8-WIP"
    mod = (donor / "kernelsu-next/out/kernelsu-next-zzi8-v3.4.0"
           / "android13-5.15_kernelsu.ko")
    donor_btf = donor / "firmware/vmlinux_ZZI8.btf"
    target = Path.home() / "rmg-firmware/gzif-contracts/s918ngzif-WIP"
    firmware = target / "firmware"
    report_path = target / "kernelsu-donor-static-audit.json"
    required = {
        "donor module": mod,
        "donor BTF": donor_btf,
        "GZIF kernel kallsyms": firmware / "kallsyms_S918NGZIF.kallsyms",
        "GZIF kernel ELF": firmware / "vmlinux_S918NGZIF.elf",
        "GZIF kernel BTF": firmware / "vmlinux_S918NGZIF.btf",
    }
    for label, file in required.items():
        if not file.is_file():
            print(f"[ERROR] Missing {label}: {file}", file=sys.stderr)
            return 2
    actual_hash = hashlib.sha256(mod.read_bytes()).hexdigest()
    if actual_hash != DONOR_SHA256:
        print(f"[ERROR] Donor module SHA-256 does not match known ZZI8 artifact: {actual_hash}",
              file=sys.stderr)
        return 2
    try:
        audit = audit_module(
            mod,
            target_release=RELEASE,
            kallsyms=required["GZIF kernel kallsyms"],
            vmlinux=required["GZIF kernel ELF"],
            target_btf=required["GZIF kernel BTF"],
            donor_btf=donor_btf,
            llvm_nm=executable("llvm-nm"),
            pahole=executable("pahole"),
            modinfo=executable("modinfo"),
            modprobe=executable("modprobe"),
            require_layout_check=True,
        )
    except (BopeError, OSError, ValueError, KeyError) as exc:
        print(f"[ERROR] Offline compatibility audit incomplete: {exc}", file=sys.stderr)
        return 2
    audit["evaluation"] = "ORIGINAL_ZZI8_DONOR_ONLY_NOT_RETARGETED"
    audit["target_release"] = RELEASE
    audit["warning"] = (
        "Never load this unmodified donor module on GZIF. CRC/symbol/BTF "
        "comparisons are host-only and do not establish KernelSU compatibility "
        "or device safety."
    )
    report_path.write_text(json.dumps(audit, sort_keys=True, indent=2) + "\n")
    print("Donor module SHA-256: MATCH")
    print("Donor ELF: AArch64 (checked separately with readelf)")
    print("Vermagic matches target:", audit["vermagic"].startswith(RELEASE + " "))
    print("Undefined symbols:", audit["undefined_symbols"])
    print("Undefined symbols missing from kernel:", len(audit["missing_symbols"]))
    print("Module version entries:", audit["module_version_entries"])
    print("Matched target CRC entries:", audit["matched_symbol_crcs"])
    print("CRC mismatches:", len(audit["crc_mismatches"]))
    print("CRC targets missing:", len(audit["missing_crc_targets"]))
    print("Layout evidence:", audit["layout_check"])
    print("BTF layout mismatches:", len(audit["btf_mismatches"]))
    print("struct module relocation mismatches:", len(audit["relocation_mismatches"]))
    print("Compatibility passed:", audit["passed"], "(original donor expected: False)")
    print("Offline report:", report_path)
    print("Status: READ-ONLY STATIC AUDIT; no root module is approved for GZIF")
    return 0  # Report generation successful; compatibility remains represented in JSON.


if __name__ == "__main__":
    raise SystemExit(main())
