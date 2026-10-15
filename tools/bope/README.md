# BOPE from OTA

`bope-from-ota` turns a Samsung incremental OTA into a complete BOPE target.
The normal path needs only the ZIP:

```sh
./tools/bope-from-ota "/home/matias/Downloads/S23 Ultra ZZHL-ZZI8.zip"
```

For that example, the command reads the ZZHL source and ZZI8 target identities
from OTA metadata. ZZI8 is the latest One UI 9 Beta 2 firmware. The pipeline
finds `targets/zzhl/` as the donor, locates `boot_ZZHL.img` by its SHA-1, and
writes `targets/zzi8-WIP/`. An existing target is never overwritten.

The pipeline does the full mechanical port:

1. Parses Samsung metadata and the exact `boot.img.p` operation.
2. Finds and validates the source boot image by size and SHA-1.
3. Applies the OTA's BSDIFF40 delta and verifies the rebuilt target boot.
4. Unpacks the boot image and recovers kallsyms plus a symbolized vmlinux.
5. Extracts embedded BTF and derives every known BOPE symbol, field, size, and
   target identity into `src/target.h`.
6. Verifies the generated contract independently against ELF and BTF.
7. Copies the shared engine/helper, builds BOPE, runs focused host regressions,
   and builds the helper, stability launcher, and mm factory.
8. Retargets the donor KernelSU Next module, checks vermagic, undefined
   symbols, modversion CRCs, and the BTF layouts KernelSU depends on, then
   rebuilds `ksud` with the audited module embedded.
9. Writes `app-profile.json`, `port-manifest.json`, hashes, compatibility
   evidence, and logs before atomically publishing the new `*-WIP` directory.

The generated target stays WIP because allocator/timing calibration inherited
from the donor still requires clean-reboot testing on the real device. A failed
gate removes the staging directory, and no partial target is published. Use
`--keep-failed` when the intermediate evidence is useful for debugging.

The tools auto-discover Android's `unpack_bootimg`, `llvm-nm`, `pahole`, the
local `kallsyms-finder`/`vmlinux-to-elf` environment, Android NDK
`28.2.13676358`, and KernelSU Next v3.4.0 source. Every path can also be passed
explicitly; see `./tools/bope-from-ota --help`.

To copy the final artifacts into the Android app and add the exact-match target
profile after all build and compatibility gates pass:

```sh
./tools/bope-from-ota firmware-update.zip --integrate-app
```

For focused development, `--skip-build` and `--skip-kernelsu` stop after the
firmware contract stage. They are intentionally not part of the default flow.

Verify any generated contract again with:

```sh
./tools/bope-verify-target \
  --header targets/example-WIP/brazilian-open-payload-engine/src/target.h \
  --elf targets/example-WIP/firmware/vmlinux_EXAMPLE.elf \
  --btf targets/example-WIP/firmware/vmlinux_EXAMPLE.btf
```

## Extracted standalone Samsung boot.img.lz4 (WIP input)

If you have only `boot.img.lz4` from a known AP package, the same
`bope-from-factory` command now accepts the extracted LZ4 file directly.
This input mode validates the supplied Samsung release-keys fingerprint, the
LZ4 and Android boot magic, and verifies that the unpacked kernel release ends
with the exact firmware build. Supply `--expected-kernel-release` to enforce
the **complete** release identity:

```sh
./tools/bope-from-factory ./boot.img.lz4 \
  --fingerprint 'samsung/dm3qksx/dm3q:17/CP2A.260605.016/S918NKSU8GZIF:user/release-keys' \
  --expected-kernel-release '5.15.197-android13-8-34343818-abS918NKSU8GZIF' \
  --donor targets/zzhl \
  --engine-donor targets/zzi8-WIP \
  --target-slug s918ngzif \
  --skip-kernelsu --skip-build
```

This route does **not** verify full Odin package provenance or signatures.
The submitted fingerprint and expected kernel release must be independently
verified from a trusted device/firmware source. The usual downstream symbol,
ELF/BTF, KernelSU and device-testing gates **still apply**. With skip flags
it produces only a candidate firmware contract, not a working root binary;
never advertise it as a supported app target.

If you already have a raw BTF blob, you can separately audit the kernel's
struct field offsets, sizes and enums, and compare them with the donor:

```sh
python3 tools/bope-btf-audit /path/to/vmlinux-GZIF.btf \
  --donor-header targets/zzi8-WIP/brazilian-open-payload-engine/src/target.h \
  --output /tmp/gzif-abi.json
```

BTF comparison does not establish static kernel symbol addresses. See the
read-only [GZIF ABI report](../../ports/S918NKSU8GZIF/btf-abi-report.json).

## Full Odin factory packages

Use `bope-from-factory` when the input is a Samsung factory ZIP containing a
nested `AP_...tar.md5`, not an incremental OTA:

```sh
./tools/bope-from-factory firmware.zip \
  --donor targets/afzh3 \
  --engine-donor targets/zzi8-WIP \
  --fingerprint samsung/dm3qxxx/dm3q:16/BUILD_ID/INCREMENTAL:user/release-keys
```

The command streams only `boot.img.lz4` from the nested AP archive, verifies
the exact supplied fingerprint against the AP build and Android generation,
then runs the same ELF/BTF contract, build, KernelSU, manifest, transaction,
and optional app-integration gates as the OTA path. A legacy donor may expose
its canonical contract under `reference/kernel/modern-target/target.h`.
