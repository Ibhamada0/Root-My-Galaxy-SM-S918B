# GZIF BOPE → KernelSU Next root-chain status

**Target:** Samsung Galaxy S23 Ultra SM-S918N, firmware
`S918NKSU8GZIF`, kernel
`5.15.197-android13-8-34343818-abS918NKSU8GZIF`.

**Status (2026-10-15): WIP. No kernel exploit, temporary root or KernelSU
load was performed or observed on the physical SM-S918N.**

## Exact chain in the existing source

1. `stability-launcher` checks runtime resources then starts BOPE with
   `LD_PRELOAD`. Owner **passed `--check-only`**, not exploit execution.
2. `00_orchestrator.c` resolves KASLR, grooms a kernel slab target,
   exercises a futex PI path, and attempts kernel address reads/writes.
   **All kernel-mutation runtime phases are unvalidated for GZIF.**
3. `10_workqueue_umh_root.c` writes to kernel addresses including
   the `CONFIG_STATIC_USERMODEHELPER_PATH` value and the SELinux
   enforcing state. A successful temporary-root socket
   `/data/local/tmp/temp_su.sock` is **not** proof of KernelSU.
   An abrupt kernel crash can interrupt the restoration procedure.
4. `helper/su_daemon.c` handles a **separate** late-load command,
   using the executable `/data/local/tmp/ksud-selected`.
   It invokes the pinned KMI string `android13-5.15`, waits for
   the KernelSU control driver, validates the `KSU` control API and
   requests restoration of SELinux Enforcing. None of this has run
   on GZIF.
5. Root is not considered **KernelSU-ready** until the module is
   loaded, the control API handshake succeeds, and SELinux is
   confirmed Enforcing. `BOOT/FLASH/APK READY` would be a false
   status at present.

## Concrete GZIF-specific gap

The fork contains a **prebuilt donor** ZZI8 KernelSU Next v3.4.0
`android13-5.15_kernelsu.ko`, plus a local, **analysis-only**
GZIF `vermagic` text replacement. Neither is a module built against
GZIF's exact supported kernel build. The repository does **not**
include the full KernelSU Next source tree, a reproducible
GZIF-specific `kernelsu.ko` build or a verified `ksud-selected`
containing that custom module.

The **upstream v3.4.0 source** exists at:
https://github.com/KernelSU-Next/KernelSU-Next/tree/v3.4.0

Its LKM build workflow is pinned at:
https://github.com/KernelSU-Next/KernelSU-Next/blob/v3.4.0/.github/workflows/ddk-lkm.yml
and uses `CONFIG_KSU=m CC=clang make` against a DDK KMI source
and build environment. The upstream v3.4.0 userspace `build.sh`
explicitly requires copying the `android13-5.15_kernelsu.ko`
asset into the `ksud` embedded assets **before** building
the loader:
https://github.com/KernelSU-Next/KernelSU-Next/blob/v3.4.0/build.sh

**A generic android13-5.15 DDK build alone is not an exact Samsung
GZIF kernel module**. The target GKI build provenance/KMI,
Samsung module loading and protected-export policy, signing,
relocations and actual load admission must be validated separately.
139 matched CRCs and eight BTF checks do not establish admission.

## Source preparation on Ubuntu WSL

The repository now contains
`tools/linux/prepare-gzif-kernelsu-source.sh`. This checks out the
**exact upstream v3.4.0 release commit** (`1a879d6` prefix),
separately from the BOPE port, and records the source identity:

```bash
cd ~/Root-My-Galaxy-GZIF
git pull --ff-only origin port/s918n-gzif-android17
bash tools/linux/prepare-gzif-kernelsu-source.sh
```

This is **actual module source preparation**, not another on-device
stability test. It does **not** build an exact GZIF module, and it
does not copy, load or flash anything on the phone. A source tree
for the exact GZIF kernel/DDK build environment is still required.

## Exact-kernel module build gate

A source-only WSL builder was added:

[`tools/linux/build-gzif-kernelsu-module-wip.sh`](../../tools/linux/build-gzif-kernelsu-module-wip.sh)

It accepts **one** `KDIR` argument and refuses to compile if the
prepared kernel build does not contain the exact GZIF release in
`include/config/kernel.release` and `include/generated/utsrelease.h`,
the live-device-compatible module Kconfig settings,
`Module.symvers`, `vmlinux`, generated configuration and an executable
`scripts/mod/modpost`. It validates the pinned upstream source commit,
copies KernelSU to a disposable host workspace, and builds through
Kbuild without modifying the phone.

```bash
# Run ONLY after obtaining an independently matched, fully prepared
# SM-S918N / S918NKSU8GZIF kernel build directory with Module.symvers.
bash tools/linux/build-gzif-kernelsu-module-wip.sh /actual/prepared/GZIF-KDIR
```

A firmware AP archive or an extracted `boot.img`/`vmlinux` is **not**
a Kbuild tree. Raw Samsung GPL kernel source alone generally also
lacks the generated artifacts or matching `Module.symvers`; a
reproducible matching kernel build is required first.
Samsung publishes mobile kernel source packages through its
[Open Source Release Center](https://opensource.samsung.com/).
Search for `SM-S918N` and the exact `S918NKSU8GZIF` version;
**availability of this exact version was not confirmed**. If not
available, the site's
[Source-code inquiry](https://opensource.samsung.com/requestInquiry)
offers a request channel.

Even if Kbuild finishes and the output has matching `vermagic`, a
device-specific rebuild is **not** proof of module acceptance or
stability. The resulting `.ko` remains WIP/off-device, and the
source-to-running-binary provenance, GKI protected-export policy,
Samsung module signing/admission, and `ksud` integration remain open.

## Implementation order (no repeat of completed smoke tests)

1. Identify the actual target GKI toolchain/build configuration
   required for a reproducible **source-built** `kernelsu.ko` for
   SM-S918N/GZIF. Keep the local vermagic-only donor module
   analysis-only and off-device.
2. Verify that the exact KernelSU module is suitable for
   late-load with GZIF's `CONFIG_MODULE_SIG_PROTECT=y` policy.
   Do not treat `CONFIG_MODULE_SIG_FORCE=n` as automatic
   module-load approval.
3. Embed the candidate target module into the **same**
   KernelSU Next v3.4.0 `ksud` build expected by
   `helper/su_daemon.c`, with a recorded source SHA, exact
   target identity and module SHA.
4. Independently review the KASLR trace ring protocol and the
   inherited allocator/futex timing before authorizing BOPE
   kernel mutation. `--check-only` pass does not cover them.
5. Define unambiguous outcomes: **KASLR found**, **kernel read/write
   working**, **temporary root helper ready**, **KernelSU admitted**,
   **KernelSU control verified**, and **SELinux Enforcing restored**.
   Each is a separate milestone, not a single `PASS`.

## Hard limitations

The GZIF one-shot branch compiles host-side but has not been
device-validated. KASLR uses **global TraceFS** after isolated
instances were denied on the physical phone; it can consume
existing raw trace events. The BOPE root stage **temporarily
modifies SELinux and kernel static UMH state**. Source overlays
limit the number of attempts and avoid truncating the global trace,
but do not make an unsafe kernel pointer or missing cleanup safe.

Do not flash, load `.ko` or run the root exploit based on the
host-only build report.
