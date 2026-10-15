# SM-S918N / S918NKSU8GZIF — BOPE port preparation

**Status: NOT PORTED / NOT FLASHABLE / DEVICE VALIDATION REQUIRED.**

Target: Samsung Galaxy S23 Ultra SM-S918N, dm3q, Android 17 / One UI 9.

- Exact fingerprint: `samsung/dm3qksx/dm3q:17/CP2A.260605.016/S918NKSU8GZIF:user/release-keys`
- Exact kernel release: `5.15.197-android13-8-34343818-abS918NKSU8GZIF`
- Kernel version info: `#1 SMP PREEMPT Mon Sep 28 01:56:16 UTC 2026`
- boot header: v4, image size: 100663296 bytes, kernel size: 46860800 bytes
- supplied LZ4 SHA-256: `c7f37c99b54a8a164b082a88af5a833f7f48bcd4ca98db9dbd8b4192e984253b`
- decompressed boot SHA-256: `1552a1dbf45a95ef25626097605c2f1d3e64c1b557353887b905be1ea166635e`
- embedded BTF: 6098807 bytes, SHA-256: `8596ca24a2316e4d52a30f206bba1adf733d3e61ecca5c760222e284caef1a2b`

The standalone boot image was inspected locally, its kernel identity was checked, and the
embedded BTF was validated with `pahole -F btf -C task_struct`. This does **not**
establish a working BOPE or KernelSU port.

## Generate a WIP target from the supplied standalone LZ4

Use the full upstream source checkout and prerequisite tools described in
[the upstream porting guide](https://github.com/soumarcelino/Root-My-Galaxy-SM-S918B/blob/main/tools/bope/README.md).

```sh
./tools/bope-from-factory "/path/to/boot.img.lz4" \
  --fingerprint 'samsung/dm3qksx/dm3q:17/CP2A.260605.016/S918NKSU8GZIF:user/release-keys' \
  --donor targets/zzhl \
  --engine-donor targets/zzi8-WIP \
  --target-slug s918ngzif \
  --skip-kernelsu --skip-build
```

This generates a *candidate* contract using the actual target kernel, not
copied offsets. To build, audit KernelSU and integrate into the app, remove the
skip flags **only after** kernel symbol extraction, ELF/BTF verification, module
ABI audit and controlled device testing are ready. The automatic app integration
must not happen while the payload is unverified.

The boot file, extracted private firmware contents, and prebuilt root binaries
are intentionally not uploaded to this public branch. The app manifest is also
intentionally unchanged: registering an incomplete target as supported would
cause an unsafe false-positive.

The source project and BOPE credits belong to
[soumarcelino/Root-My-Galaxy-SM-S918B](https://github.com/soumarcelino/Root-My-Galaxy-SM-S918B).
