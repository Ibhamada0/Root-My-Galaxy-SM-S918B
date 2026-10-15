#!/usr/bin/env python3
"""Offline-only triage of non-prefixed inherited GZIF contract macros.

Uses the owner's local generated WIP contract and BTF, never ADB/device access.
A passing report validates ONLY a handful of structural invariants; it does
not validate the exploit, device-calibrated offsets, or KernelSU.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.bope.contract import (  # noqa: E402
    STATIC_UMH_GUARD,
    btf_layout,
    field_offset,
    parse_numeric_macros,
    structure_size,
)

CATEGORIES = {
    "abi_geometry_pending_review": (
        "TARGET_FILE_CACHE_SIZE",
        "TARGET_ORDER3_SIZE",
        "TARGET_PAGE_MASK",
        "TARGET_PAGE_SIZE",
        "TARGET_RB_LEFT_OFF",
        "TARGET_RB_PARENT_OFF",
        "TARGET_RB_RIGHT_OFF",
        "TARGET_STRSCPY_WORD_SIZE",
        "TARGET_TTY_MAGIC",
        "TARGET_WORK_PENDING_BIT",
    ),
    "runtime_specific_unverified": (
        "TARGET_KERNEL_IMAGE_SPAN",
        "TARGET_KMALLOC_4K_CACHE_NAME",
        "TARGET_LIVE_TO_BUFFER_DELTA",
        "TARGET_LOCK_WAITERS_SELF_LIVE_OFF",
        "TARGET_PI_WAITERS_SELF_LIVE_OFF",
        "TARGET_PRIMARY_FOPS_BUFFER_OFF",
        "TARGET_PRIMARY_FOPS_LIVE_OFF",
        "TARGET_RECOVERY_FOPS_BUFFER_OFF",
        "TARGET_RECOVERY_FOPS_LIVE_OFF",
        "TARGET_ROOT_TTY_OPS_LIVE_OFF",
        "TARGET_ROOT_UMH_DATA_LIVE_OFF",
        "TARGET_TRACE_CALLER_OFF",
        "TARGET_TRACE_LOOSE_RECORD_SIZE",
        "TARGET_TRACE_SCHED_BLOCKED_REASON_ID",
        "TARGET_TRACE_TYPE_LEN_MASK",
        "TARGET_WAITER_LOCK_LIVE_OFF",
    ),
    "bootstrap_and_timing_unverified": (
        "TARGET_BINFMT_TRIGGER_PATH",
        "TARGET_STATIC_UMH_GUARD_SIZE",
        "TARGET_STATIC_UMH_PATCH_SIZE",
        "TARGET_STATIC_UMH_PATH",
        "TARGET_UMH_SOCKET_POLL_COUNT",
        "TARGET_UMH_SOCKET_POLL_USEC",
        "TARGET_UMH_TRIGGER_TIMEOUT_MS",
    ),
}
EXCLUDED_PREFIXES = (
    "TARGET_FUTEX_", "TARGET_RETRY_", "TARGET_ATTEMPT_",
    "TARGET_MM_", "TARGET_RECLAIM_", "TARGET_KSNITCH_", "TARGET_SKB_",
    "TARGET_PIPE_", "TARGET_CONFIGFS_", "TARGET_ASHMEM_",
    "TARGET_KASLR_", "TARGET_LINEAR_MAP_", "TARGET_VMEMMAP_",
    "TARGET_FAKE_", "TARGET_SIGNAL_", "TARGET_RT_WAITER_",
)


def audit(target: Path) -> dict:
    manifest = json.loads((target / "port-manifest.json").read_text())
    if manifest["target"]["build"] != "S918NKSU8GZIF":
        raise ValueError("Refusing non-GZIF target manifest")
    if manifest["status"] != "GENERATED_WIP_DEVICE_VALIDATION_REQUIRED":
        raise ValueError("Unexpected target status; never audit as supported")
    header = target / "brazilian-open-payload-engine/src/target.h"
    btf = target / "firmware/vmlinux_S918NGZIF.btf"
    if not header.is_file() or not btf.is_file():
        raise FileNotFoundError("Local generated header or GZIF BTF is missing")
    inherited = set(manifest["contract"]["inherited_calibration_values"])
    other = {name for name in inherited if not name.startswith(EXCLUDED_PREFIXES)}
    known = set().union(*(set(names) for names in CATEGORIES.values()))
    if other != known:
        raise ValueError(
            f"Unrecognized inherited macros: missing={sorted(known - other)} "
            f"unexpected={sorted(other - known)}; review categorization first"
        )

    numbers = parse_numeric_macros(header)
    header_text = header.read_text()
    import re
    path_match = re.search(
        r'^#define\s+TARGET_STATIC_UMH_PATH\s+"([^"]+)"\s*$',
        header_text, re.MULTILINE,
    )
    if not path_match:
        raise ValueError("Missing literal TARGET_STATIC_UMH_PATH")
    umh_path = path_match.group(1)
    pahole = shutil.which("pahole")
    if not pahole:
        raise FileNotFoundError("pahole executable not found")

    checks = []
    def expect(label: str, macro: str, actual: int, expected: int | None):
        checks.append({
            "check": label, "macro": macro,
            "contract_value": actual, "independently_observed": expected,
            "passed": expected is not None and actual == expected,
        })

    file_layout = btf_layout(btf, "file", Path(pahole))
    expect("BTF struct file size", "TARGET_FILE_CACHE_SIZE",
           numbers["TARGET_FILE_CACHE_SIZE"], structure_size(file_layout))
    rb_layout = btf_layout(btf, "rb_node", Path(pahole))
    for macro, member in (
        ("TARGET_RB_PARENT_OFF", "__rb_parent_color"),
        ("TARGET_RB_RIGHT_OFF", "rb_right"),
        ("TARGET_RB_LEFT_OFF", "rb_left"),
    ):
        expect(f"BTF rb_node.{member} offset", macro,
               numbers[macro], field_offset(rb_layout, member))
    expect("Static helper guard byte count", "TARGET_STATIC_UMH_GUARD_SIZE",
           numbers["TARGET_STATIC_UMH_GUARD_SIZE"], len(STATIC_UMH_GUARD))
    # Geometry check only, NOT authorization to modify this kernel string.
    patch_size = numbers["TARGET_STATIC_UMH_PATCH_SIZE"]
    checks.append({
        "check": "Static helper path fits inherited patch buffer",
        "macro": "TARGET_STATIC_UMH_PATCH_SIZE",
        "contract_value": patch_size,
        "independently_observed": len(umh_path.encode("utf-8")) + 1,
        "passed": len(umh_path.encode("utf-8")) + 1 <= patch_size
        <= len(STATIC_UMH_GUARD),
    })
    return {
        "schema": 1,
        "status": "OFFLINE_TRIAGE_ONLY_UNVERIFIED",
        "target_build": "S918NKSU8GZIF",
        "category_counts": {key: len(names) for key, names in CATEGORIES.items()},
        "categories": {key: list(names) for key, names in CATEGORIES.items()},
        "total_other_inherited": len(other),
        "checks": checks,
        "passed_checks": sum(item["passed"] for item in checks),
        "failed_checks": [item for item in checks if not item["passed"]],
        "warning": (
            "Only six structural checks; all 33 inherited definitions still "
            "require source-specific assessment. Live offsets, trace IDs, "
            "KASLR, timing, exploit and KernelSU behavior are NOT validated."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=(
        Path.home() / "rmg-firmware/gzif-contracts/s918ngzif-WIP"
    ))
    args = parser.parse_args()
    try:
        report = audit(args.target.expanduser())
    except (OSError, KeyError, ValueError, RuntimeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    output = args.target.expanduser() / "inherited-offline-audit.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("GZIF inherited macros: " + str(report["total_other_inherited"]))
    for category, count in report["category_counts"].items():
        print(f"  {category}: {count}")
    print(f"Offline structural checks: {report['passed_checks']}/{len(report['checks'])}")
    for item in report["failed_checks"]:
        print(f"  [FAIL] {item['check']}: expected {item['independently_observed']}, "
              f"header {item['contract_value']}")
    print(f"Report: {output}")
    print("Status: OFFLINE TRIAGE ONLY — Root payload NOT validated")
    return 1 if report["failed_checks"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
