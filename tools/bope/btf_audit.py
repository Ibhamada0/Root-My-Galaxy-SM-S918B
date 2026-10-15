"""Read-only BTF ABI audit for BOPE firmware ports.

This does not derive kernel symbol addresses, calibrate an exploit, build
payloads or confirm that a device can be rooted. All unsupported values remain
unresolved instead of being copied silently from the donor target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

from .contract import (
    BTF_ENUM_CONSTANTS,
    BTF_FIELDS,
    BTF_SIZES,
    btf_layout,
    enum_values,
    field_offset,
    parse_numeric_macros,
    structure_size,
)
from .errors import BopeError


def audit_btf(btf: Path, *, donor_header: Path | None = None) -> dict:
    btf = btf.expanduser().resolve()
    if not btf.is_file():
        raise BopeError(f"BTF does not exist: {btf}")
    if btf.open("rb").read(4) != b"\x9f\xeb\x01\x00":
        raise BopeError("input is not a raw, little-endian BTF blob")
    if not shutil.which("pahole"):
        raise BopeError("pahole is required for the BTF ABI audit")

    layouts: dict[str, str] = {}
    def layout(structure: str) -> str:
        if structure not in layouts:
            layouts[structure] = btf_layout(btf, structure, Path("pahole"))
        return layouts[structure]

    values: dict[str, int] = {}
    missing: list[str] = []
    for macro, (structure, member) in BTF_FIELDS.items():
        offset = field_offset(layout(structure), member)
        if offset is None:
            missing.append(macro)
        else:
            values[macro] = offset
    for macro, structure in BTF_SIZES.items():
        size = structure_size(layout(structure))
        if size is None:
            missing.append(macro)
        else:
            values[macro] = size

    enums: dict[str, dict[str, int]] = {}
    for macro, (enum_name, member) in BTF_ENUM_CONSTANTS.items():
        if enum_name not in enums:
            enums[enum_name] = enum_values(btf, Path("pahole"), enum_name)
        value = enums[enum_name].get(member)
        if value is None:
            missing.append(macro)
        else:
            values[macro] = value

    comparison = None
    if donor_header is not None:
        donor_header = donor_header.expanduser().resolve()
        if not donor_header.is_file():
            raise BopeError(f"baseline target header does not exist: {donor_header}")
        donor_values = parse_numeric_macros(donor_header)
        absent = sorted(name for name in values if name not in donor_values)
        differences = {
            name: {"target": value, "baseline": donor_values[name]}
            for name, value in sorted(values.items())
            if name in donor_values and value != donor_values[name]
        }
        comparison = {
            "baseline_path": str(donor_header),
            "compared": len(values) - len(absent),
            "matched": len(values) - len(absent) - len(differences),
            "differences": differences,
            "missing_in_baseline": absent,
        }
    return {
        "status": "BTF_ABI_ONLY_NO_ELF_SYMBOLS_OR_DEVICE_VALIDATION",
        "sha256": hashlib.sha256(btf.read_bytes()).hexdigest(),
        "bytes": btf.stat().st_size,
        "resolved_count": len(values),
        "missing": sorted(missing),
        "expected_count": len(BTF_FIELDS) + len(BTF_SIZES) + len(BTF_ENUM_CONSTANTS),
        "baseline": comparison,
        "macros": dict(sorted(values.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("btf", type=Path, help="extracted raw vmlinux BTF file")
    parser.add_argument("--donor-header", type=Path, help="baseline src/target.h")
    parser.add_argument("--output", type=Path, help="JSON report destination")
    args = parser.parse_args(argv)
    try:
        result = audit_btf(args.btf, donor_header=args.donor_header)
    except (BopeError, OSError, ValueError) as error:
        print(f"bope-btf-audit: {error}", file=sys.stderr)
        return 1
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 2 if result["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
