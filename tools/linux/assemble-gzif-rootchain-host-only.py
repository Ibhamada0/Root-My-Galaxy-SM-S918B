#!/usr/bin/env python3
"""Assemble the five finished GZIF Android host artifacts with provenance.

OFF-DEVICE ONLY. This is NOT a root/install/deploy package. It never
executes the artifacts, uses ADB, flashes or loads any kernel module.
No regression, stability or KASLR tests are repeated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

BUILD = "S918NKSU8GZIF"
RELEASE = "5.15.197-android13-8-34343818-abS918NKSU8GZIF"
KSU_COMMIT = "1a879d6a866f80b1fa1c1009a2ffa747873cbb5e"
HOME = Path.home()
DEFAULT_BOPE = (
    HOME / "rmg-firmware/gzif-android-builds/s918ngzif-7cjfl28m/build-report.json"
)
DEFAULT_KSUD = (
    HOME / "rmg-firmware/gzif-kernelsu-loader-builds/"
    "s918ngzif-ksud-ohhjnre7/build-report.json"
)
DEFAULT_OUTPUT = (
    HOME / "rmg-firmware/gzif-rootchain-host-only/"
    "s918n-gzif-bope-ksud-candidate"
)
AUDIT = (
    HOME / "rmg-firmware/gzif-contracts/s918ngzif-WIP/"
    "analysis-only/kernelsu-gzif-metadata-static-audit.json"
)
ARTIFACTS = {
    "payload_so": "payload.so",
    "mm_exec_factory": "mm-exec-factory",
    "stability_launcher": "stability-launcher-s918ngzif",
    "root_helper": "cve-2026-43499-root",
}
LOADER_NAME = "ksud-selected.WIP"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_elf(path: Path) -> None:
    with path.open("rb") as stream:
        head = stream.read(64)
    # ELF64 little-endian, e_machine = EM_AARCH64 (183).
    require(
        len(head) == 64
        and head[:4] == b"\x7fELF"
        and head[4] == 2
        and head[5] == 1
        and int.from_bytes(head[18:20], "little") == 183,
        f"Not an ELF64/AArch64 build artifact: {path}",
    )


def json_object(path: Path) -> dict:
    require(path.is_file(), f"Report missing: {path}")
    data = json.loads(path.read_text())
    require(isinstance(data, dict), f"Report is not a JSON object: {path}")
    return data


def verify_item(
    source: Path, recorded_hash: object, recorded_size: object,
    expected_parent: Path,
) -> dict:
    require(source.is_file(), f"Missing previously built artifact: {source}")
    require(
        source.resolve().is_relative_to(expected_parent.resolve()),
        f"Artifact must come from its declared build workspace: {source}",
    )
    verify_elf(source)
    digest = sha256(source)
    require(
        isinstance(recorded_hash, str) and digest == recorded_hash,
        f"SHA-256 differs from original build report: {source}",
    )
    require(
        type(recorded_size) is int and source.stat().st_size == recorded_size,
        f"Size differs from original build report: {source}",
    )
    return {"source": str(source), "sha256": digest, "size": recorded_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bope-report", type=Path, default=DEFAULT_BOPE)
    parser.add_argument("--ksud-report", type=Path, default=DEFAULT_KSUD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    staging: Path | None = None
    try:
        bope_path = args.bope_report.expanduser().resolve()
        ksud_path = args.ksud_report.expanduser().resolve()
        destination = args.output.expanduser().resolve()
        bope = json_object(bope_path)
        ksud = json_object(ksud_path)
        audit = json_object(AUDIT)

        require(
            bope.get("status")
            == "HOST_BUILD_ONE_SHOT_EXPERIMENTAL_NOT_DEVICE_VALIDATED",
            "Expected the owner-confirmed guarded BOPE build, not donor/full-exploit",
        )
        require(
            bope.get("firmware") == BUILD
            and bope.get("kernel_release") == RELEASE,
            "BOPE report target mismatch",
        )
        require(
            isinstance(bope.get("one_shot_overlay"), dict)
            and bope["one_shot_overlay"].get("mode")
            == "ONE_SHOT_GZIF_EXPERIMENTAL_NOT_DEVICE_VALIDATED",
            "BOPE one-shot guard missing",
        )
        require(
            isinstance(bope.get("root_chain"), dict)
            and bope["root_chain"].get("full_root_ready") is False,
            "Unexpected BOPE root-ready report; stop and inspect",
        )
        require(
            ksud.get("status")
            == "HOST_BUILT_KSUD_WITH_ZZI8_DONOR_METADATA_GZIF_WIP_NOT_DEVICE_VALIDATED",
            "Expected the exact host-only donor-derived ksud report",
        )
        require(
            ksud.get("firmware") == BUILD
            and ksud.get("kernel_release") == RELEASE
            and ksud.get("source_commit") == KSU_COMMIT
            and ksud.get("embedded_asset") == "android13-5.15_kernelsu.ko",
            "KernelSU builder source/KMI/firmware mismatch",
        )
        require(
            audit.get("passed") is True
            and audit.get("evaluation") == "METADATA_ONLY_LOCAL_WIP_CANDIDATE"
            and audit.get("status") == "NOT_DEVICE_VALIDATED_NOT_APPROVED_TO_LOAD"
            and ksud.get("module_sha256") == audit.get("sha256"),
            "Loader's embedded module hash does not match the audited candidate",
        )

        originals: dict[str, tuple[Path, dict]] = {}
        artifacts = bope.get("artifacts")
        require(isinstance(artifacts, dict), "Missing BOPE artifacts table")
        for key, name in ARTIFACTS.items():
            metadata = artifacts.get(key)
            require(isinstance(metadata, dict), f"Missing BOPE build output: {key}")
            source = Path(str(metadata.get("path", ""))).resolve()
            require(source.name == name, f"Unexpected {key} filename")
            verified = verify_item(
                source, metadata.get("sha256"), metadata.get("size"),
                bope_path.parent,
            )
            originals[name] = (source, verified)

        loader = Path(str(ksud.get("loader_path", ""))).resolve()
        require(loader.name == LOADER_NAME, "Unexpected ksud output name")
        verified_loader = verify_item(
            loader, ksud.get("loader_sha256"), ksud.get("loader_bytes"),
            ksud_path.parent,
        )
        originals[LOADER_NAME] = (loader, verified_loader)

        # Verify the actual built helper's expected late-load strings, rather
        # than assuming the current donor source equals the compiled binary.
        helper_bytes = originals["cve-2026-43499-root"][0].read_bytes()
        for expected in (
            b"/data/local/tmp/ksud-selected",
            b"android13-5.15",
            b"com.rifsxd.ksunext",
        ):
            require(expected in helper_bytes,
                    f"Compiled helper missing expected KernelSU late-load string: {expected!r}")

        require(not destination.exists(), f"Output already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(
            prefix=".s918ngzif-host-only-", dir=destination.parent
        ))
        files = staging / "HOST_ONLY_NOT_FOR_DEVICE"
        files.mkdir()

        entries: dict[str, dict] = {}
        for name, (source, original_info) in originals.items():
            target = files / name
            shutil.copyfile(source, target)
            target.chmod(0o600)  # Avoid accidentally treating staged files as executable.
            require(
                sha256(target) == original_info["sha256"],
                f"Staged copy changed unexpectedly: {name}",
            )
            entries[name] = {
                **original_info,
                "staged": f"HOST_ONLY_NOT_FOR_DEVICE/{name}",
            }

        manifest = {
            "status": "HOST_ARTIFACTS_ASSEMBLED_NOT_ROOT_READY_DO_NOT_DEPLOY",
            "device": "Samsung Galaxy S23 Ultra SM-S918N",
            "firmware": BUILD,
            "kernel_release": RELEASE,
            "bope_build_report": str(bope_path),
            "ksud_build_report": str(ksud_path),
            "module_audit_report": str(AUDIT),
            "module_sha256": ksud["module_sha256"],
            "module_provenance": "ZZI8 donor KernelSU Next v3.4.0; GZIF vermagic-only",
            "kernelsu_source_commit": KSU_COMMIT,
            "host_artifacts": entries,
            "observations": {
                "bope_kaslr_on_device": (
                    "OWNER_CONFIRMED two-distinct-page quorum=2; "
                    "TraceFS 0/0 before/after; not a kernel root exploit"
                ),
                "host_regressions": "OWNER_CONFIRMED 12/12 OK",
                "ksud_android_arm64_build": "OWNER_CONFIRMED BUILT",
                "kernel_rw": "NOT_VALIDATED",
                "temporary_root": "NOT_VALIDATED",
                "samsung_module_load_admission": "NOT_VALIDATED",
                "kernelsu_control_handshake": "NOT_VALIDATED",
                "selinux_restore": "NOT_VALIDATED",
                "persistent_root": "NOT_VALIDATED",
            },
            "full_root_ready": False,
            "deployable": False,
        }
        (staging / "rootchain-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        (staging / "READ_ME_FIRST.txt").write_text(
            "HOST-ONLY DEVELOPMENT EVIDENCE — NOT A FLASH/ROOT/INSTALL PACKAGE\n"
            "No files in this directory have been validated for device root.\n"
            "The KernelSU module is a donor-derived unsigned GZIF-vermagic candidate.\n"
            "No ADB, insmod, exploit run or Android installation is performed.\n"
            "See rootchain-manifest.json for source hashes and missing gates.\n"
        )
        staging.rename(destination)
        staging = None
        print(f"[ASSEMBLED] 5 Android ARM64 host artifacts: {destination}")
        print(f"Manifest: {destination / 'rootchain-manifest.json'}")
        print("Status: HOST_ONLY_NOT_ROOT_READY; no device actions")
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 2
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
