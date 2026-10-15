"""Safely accept an extracted Samsung AP boot.img.lz4 as BOPE port input.

This is an input adapter only. It does NOT generate a validated payload or
certify that KernelSU can be loaded on the target firmware.
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil

from .common import executable, run
from .errors import BopeError
from .factory import FactoryInfo


STANDALONE_AP_ENTRY = "<standalone-boot-lz4>"
LZ4_FRAME_MAGIC = b"\x04\x22\x4d\x18"
FINGERPRINT = re.compile(
    r"^samsung/[^/]+/(?P<device>[^:]+):(?P<android>[0-9]+)/"
    r"[^/]+/(?P<build>S[0-9]{3}[A-Z][A-Z0-9]+):user/release-keys$"
)


def inspect_standalone_boot(
    path: Path,
    *,
    donor_build: str,
    donor_fingerprint: str,
    target_fingerprint: str,
    device: str,
    target_slug: str | None = None,
) -> FactoryInfo:
    path = path.expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".lz4":
        raise BopeError(f"expected a standalone boot.img.lz4 file: {path}")
    with path.open("rb") as stream:
        if stream.read(4) != LZ4_FRAME_MAGIC:
            raise BopeError("standalone boot is not an LZ4 frame")
    match = FINGERPRINT.fullmatch(target_fingerprint)
    if not match:
        raise BopeError("expected an exact Samsung release-keys target fingerprint")
    if match.group("device") != device:
        raise BopeError("target fingerprint device does not match --device")
    if donor_build not in donor_fingerprint:
        raise BopeError("donor fingerprint does not contain its own build")
    if target_slug is not None and not re.fullmatch(r"[a-z0-9]+", target_slug):
        raise BopeError("target slug must contain only lowercase ASCII letters and digits")
    return FactoryInfo(
        path=path,
        ap_entry=STANDALONE_AP_ENTRY,
        boot_entry=path.name,
        device=device,
        pre_build=donor_build,
        post_build=match.group("build"),
        pre_fingerprint=donor_fingerprint,
        post_fingerprint=target_fingerprint,
        android_version=match.group("android"),
        target_slug=target_slug,
    )


def extract_standalone_boot(
    source: Path, compressed: Path, output: Path, *, lz4: Path | None = None
) -> Path:
    compressed.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == compressed.resolve():
        raise BopeError("standalone input must not be the staging output path")
    shutil.copyfile(source, compressed)
    decoder = executable("lz4", explicit=lz4)
    try:
        run([decoder, "-d", "-f", compressed, output])
        with output.open("rb") as stream:
            if stream.read(8) != b"ANDROID!":
                raise BopeError("standalone boot decompressed to non-Android content")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return output
