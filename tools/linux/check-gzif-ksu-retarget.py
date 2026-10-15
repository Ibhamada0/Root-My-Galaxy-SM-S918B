#!/usr/bin/env python3
"""Make and statically inspect a local GZIF-vermagic *candidate* module.

ANALYSIS ONLY: not an installation, signing, loading, or device validation.
Never run this artifact on a phone. No ADB commands are used.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.bope.common import executable  # noqa: E402
from tools.bope.errors import BopeError  # noqa: E402
from tools.bope.kernelsu import audit_module  # noqa: E402

DONOR_RELEASE = "5.15.197-android13-8-34343818-abS918BXXUAZZI8"
TARGET_RELEASE = "5.15.197-android13-8-34343818-abS918NKSU8GZIF"
DONOR_SHA256 = "eb518dd33f782fa4e47f58e16a7148029b96eaff98974e10067b409f9b5ff090"


def expected_metadata_only_copy(source: bytes) -> bytes:
    """Fail closed unless exactly one same-length vermagic change is possible."""
    old = ("vermagic=" + DONOR_RELEASE).encode("ascii")
    new = ("vermagic=" + TARGET_RELEASE).encode("ascii")
    if len(old) != len(new):
        raise ValueError("Source/target vermagic length differs; rebuild required")
    if source.count(old) != 1:
        raise ValueError("Expected exactly one donor vermagic field")
    if new in source:
        raise ValueError("Target vermagic unexpectedly already present in donor")
    result = source.replace(old, new, 1)
    if len(result) != len(source):
        raise AssertionError("Unexpected module size change")
    # The only permitted difference is the original in-place text substitution.
    if result.replace(new, old, 1) != source:
        raise AssertionError("Unexpected change outside vermagic")
    return result


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    target = Path.home() / "rmg-firmware/gzif-contracts/s918ngzif-WIP"
    manifest_file = target / "port-manifest.json"
    donor = (repo / "targets/zzi8-WIP/kernelsu-next/out"
             / "kernelsu-next-zzi8-v3.4.0/android13-5.15_kernelsu.ko")
    donor_btf = repo / "targets/zzi8-WIP/firmware/vmlinux_ZZI8.btf"
    firmware = target / "firmware"
    required = {
        "target manifest": manifest_file,
        "donor module": donor,
        "donor BTF": donor_btf,
        "GZIF kallsyms": firmware / "kallsyms_S918NGZIF.kallsyms",
        "GZIF vmlinux ELF": firmware / "vmlinux_S918NGZIF.elf",
        "GZIF BTF": firmware / "vmlinux_S918NGZIF.btf",
        "pre-retarget static report": target / "kernelsu-donor-static-audit.json",
    }
    for description, path in required.items():
        if not path.is_file():
            print(f"[ERROR] Missing {description}: {path}", file=sys.stderr)
            return 2

    try:
        manifest = json.loads(manifest_file.read_text())
        if manifest["status"] != "GENERATED_WIP_DEVICE_VALIDATION_REQUIRED":
            raise ValueError("Target must remain an unvalidated WIP")
        if (manifest["target"]["build"] != "S918NKSU8GZIF"
                or manifest["target"]["kernel_release"] != TARGET_RELEASE
                or manifest["contract"]["verification"]["passed"] is not True):
            raise ValueError("Target identity or contract verification does not match")
        prior = json.loads(required["pre-retarget static report"].read_text())
        if prior.get("target_release") != TARGET_RELEASE or prior.get("passed") is not False:
            raise ValueError("Expected audited unmodified donor vermagic mismatch")
        if (prior.get("missing_symbols") or prior.get("crc_mismatches")
                or prior.get("missing_crc_targets") or prior.get("btf_mismatches")
                or prior.get("relocation_mismatches") or
                prior.get("module_version_entries") != 139 or
                prior.get("matched_symbol_crcs") != 139):
            raise ValueError("Donor static audit has unresolved issues")
        donor_bytes = donor.read_bytes()
        if hashlib.sha256(donor_bytes).hexdigest() != DONOR_SHA256:
            raise ValueError("Donor module SHA-256 has changed")
        expected = expected_metadata_only_copy(donor_bytes)
        output_dir = target / "analysis-only"
        candidate = output_dir / "kernelsu-gzif-vermagic-WIP.ko"
        output_dir.mkdir(parents=True, exist_ok=True)
        if candidate.exists():
            if candidate.read_bytes() != expected:
                raise ValueError("Existing WIP module differs; refusing to overwrite")
        else:
            candidate.write_bytes(expected)
        if candidate.read_bytes() != expected:
            raise ValueError("WIP file validation failed")

        report = audit_module(
            candidate,
            target_release=TARGET_RELEASE,
            kallsyms=required["GZIF kallsyms"],
            vmlinux=required["GZIF vmlinux ELF"],
            target_btf=required["GZIF BTF"],
            donor_btf=donor_btf,
            build_module=donor,
            llvm_nm=executable("llvm-nm"),
            pahole=executable("pahole"),
            modinfo=executable("modinfo"),
            modprobe=executable("modprobe"),
            require_layout_check=True,
        )
        report["evaluation"] = "METADATA_ONLY_LOCAL_WIP_CANDIDATE"
        report["status"] = "NOT_DEVICE_VALIDATED_NOT_APPROVED_TO_LOAD"
        report["donor_sha256"] = DONOR_SHA256
        report["changed_bytes_only"] = "vermagic target release string"
        report["limitations"] = [
            "No rebuild or module signing performed",
            "Donor BTF is not module-build DWARF evidence",
            "No Samsung device load policy or signature gate verified",
            "No GZIF live runtime behavior, BOPE calibration, or KernelSU functionality tested",
            "Never insmod/flash/deploy this candidate as-is",
        ]
        report_file = output_dir / "kernelsu-gzif-metadata-static-audit.json"
        report_file.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print("Donor SHA-256: MATCH")
        print("Metadata-only modification: vermagic release only")
        print("Target vermagic matches:", report["vermagic"].startswith(TARGET_RELEASE + " "))
        print("Missing symbols:", len(report["missing_symbols"]))
        print("CRC mismatches:", len(report["crc_mismatches"]))
        print("Missing CRC targets:", len(report["missing_crc_targets"]))
        print("BTF mismatches:", len(report["btf_mismatches"]))
        print("struct module relocation mismatches:", len(report["relocation_mismatches"]))
        print("Static audit passed:", report["passed"])
        print("WIP analysis artifact:", candidate)
        print("Report:", report_file)
        print("Status: NOT DEVICE-VALIDATED — DO NOT LOAD/FLASH")
        return 0 if report["passed"] else 1
    except (BopeError, OSError, ValueError, KeyError, AssertionError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
