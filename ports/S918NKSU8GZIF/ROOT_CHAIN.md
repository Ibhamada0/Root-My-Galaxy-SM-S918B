# GZIF BOPE → KernelSU Next root-chain status

**Target:** Samsung Galaxy S23 Ultra SM-S918N, firmware
`S918NKSU8GZIF`, kernel
`5.15.197-android13-8-34343818-abS918NKSU8GZIF`.

**Status (2026-10-15): WIP. No kernel exploit, temporary root or KernelSU
load was performed or observed on the physical SM-S918N.**

## Verified live BOPE kernel-base stage — 2026-10-15

Owner-confirmed **updated GZIF KASLR-only** run on the
physical SM-S918N, with the rebuilt two-page quorum logic:

- `stage=gzif-kaslr-distinct-pages-quorum=2`
- `stage=gzif-tracefs-live-capture-ms=67`
- Kernel slide resolver `votes=2 sample_ms=2`
- `stage=gzif-kaslr-resolved root-not-attempted`
- `TraceFS before: 0/0` and `TraceFS after: 0/0`
- Process exited `0`; absolute kernel addresses **not recorded**.

The execution verifies that **the kernel-base discovery mechanism
ran and produced a candidate from separately read raw trace pages**,
not independent proof that the candidate is the true runtime text
base. This result does not validate the donor-inherited
allocator/futex exploitation chain.

**Distinct next stage:** BOPE's `do_one_attempt` requires a native
root helper and an `mm_exec_factory`, then calls
`root_umh_preflight`, `oss_prepare_kernel_rw_path`,
`cpu_discovery_select`, `kaslr_locate_via_tracefs`,
`groom_and_install_fops_object` and the futex trigger.
The UMH preflight **does real filesystem staging and an invalid
binfmt `execve`**; it is not a no-effect check.
The root helper later depends on changing the kernel's static UMH
path and SELinux enforcing state through kernel memory writes,
with cleanup paths and recovery consequences.

**The original ZZI8 KernelSU module must not be treated as a
verified GZIF loadable module**. No temporary root or KSU load
has occurred, so no automatic root-run command is published
from the KASLR-only result.

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

## Donor-version KernelSU Next ksud integration (host WIP only)

The original BOPE root helper expects the executable
`/data/local/tmp/ksud-selected`, but the four BOPE native artifacts
do **not** include this daemon. The actual **KernelSU Next v3.4.0**
`late-load` implementation retrieves the embedded
`android13-5.15_kernelsu.ko` RustEmbed asset, tries to load
it through `ksuinit::load_module`, then initializes KernelSU and
its Manager. This is a **separate step** after temporary root.

The pinned upstream `ksuinit::load_module` uses the kernel's
`init_module` syscall; it resolves undefined symbols from
`/proc/kallsyms` and has a fallback to rewrite `vermagic`
if kernel logs reveal a mismatch. **Neither fallback bypasses
Samsung's kernel module loading policy or guarantees ABI safety.**
Thus matching KMI and host-side CRC/BTF checks are useful evidence
but not proof of loadability.

### Build the missing ksud executable now, without kernel sources

The repository includes:
[`tools/linux/build-gzif-ksud-loader-wip.py`](../../tools/linux/build-gzif-ksud-loader-wip.py).

It requires the owner-prepared pinned `KernelSU-Next-v3.4.0`
checkout, the **existing audited metadata-only GZIF module candidate**
from `check-gzif-ksu-retarget.py` and its PASS report, Rust
`cargo/rustc`, and the previously installed Android NDK 28.
No Samsung Kbuild source is required for **this ksud build**.
The script stages an isolated source copy and embeds exactly
the previously audited donor-derived module; it rejects any
unrelated change to the donor binary, module, commit or helper KMI.
It then invokes Cargo to build the **real Android aarch64 ksud**,
saving the output as `ksud-selected.WIP` with SHA and provenance.

```bash
cd ~/Root-My-Galaxy-GZIF
git pull --ff-only origin port/s918n-gzif-android17
python3 tools/linux/build-gzif-ksud-loader-wip.py
```

This is **an integration build**, not another identity/stability
test. If `cargo`, its `aarch64-linux-android` Rust target,
bindgen/libclang, or the host-only audited module artifact is
missing, the build reports a concrete missing input; repair
that dependency rather than repeating successful KASLR tests.

**Do not push, execute or load `ksud-selected.WIP` or the donor
`.ko` on a device**. The embedded module is still the ZZI8
developer's binary with only a GZIF metadata-field replacement;
it is not built from Samsung GZIF kernel sources.
The module load syscall may be rejected, or a binary mismatch
may crash the device. This host integration only eliminates the
missing-ksud-build gap, not the runtime kernel-mutation gap.

### Owner-confirmed completed ksud Android ARM64 host build — 2026-10-15

The owner ran `python3 tools/linux/build-gzif-ksud-loader-wip.py`
after fixing a loader-builder audit-schema mismatch and installing
Rust/Cargo. **The actual Cargo cross-build completed successfully**:

```text
[SOURCE] KernelSU Next v3.4.0 pinned: 1a879d6a866f80b1fa1c1009a2ffa747873cbb5e
[MODULE] EXACT metadata-only donor candidate staged as embedded android13-5.15_kernelsu.ko
[BUILD] Actual Android ksud via cargo; no ADB/insmod/flash
[BUILT] ksud-selected.WIP: ELF64/AArch64 (4246104 bytes)
Status: HOST BUILT; device module admission NOT validated
```

The owner's local outputs are:

```text
~/rmg-firmware/gzif-kernelsu-loader-builds/s918ngzif-ksud-ohhjnre7/ksud-selected.WIP
~/rmg-firmware/gzif-kernelsu-loader-builds/s918ngzif-ksud-ohhjnre7/build-report.json
~/rmg-firmware/gzif-kernelsu-loader-builds/s918ngzif-ksud-ohhjnre7/ksud-cargo-build.log
```

This **closes the missing-userspace-ksud host-build gap**:
a real ARM64 Android `ksud` with the donor-derived
`android13-5.15_kernelsu.ko` embedded now exists in the owner's
WSL. It is still an **unapproved experimental build**; the kernel
module was **not source-rebuilt for GZIF**, signed, or loaded.

**The remaining chain is NOT validated:** BOPE kernel mutation,
verified arbitrary kernel R/W, temporary root via UMH, module
load admission under Samsung security policy, successful KernelSU
control handshake, SELinux restoration and persistence. No
device test/flash/load is justified just by the successful Cargo
build. Do not repeat completed 12/12 host regressions or KASLR
tests merely to confirm this host-build result.

## Five-artifact BOPE + KernelSU host-only assembly

The owner has already completed **both** the guarded BOPE native
build and the pinned KernelSU Next `ksud` Cargo cross-build.
No further host regressions or KASLR repetitions are needed merely
to put those binaries together.

`tools/linux/assemble-gzif-rootchain-host-only.py` assembles the
existing **four BOPE native binaries plus actual Android ARM64
`ksud-selected.WIP`**, using their original `build-report.json`
files and the prior positive donor-module static audit. It checks
ELF architecture, original SHA-256 and byte count, root-helper
late-load path/KMI/manager identifier in the **compiled binary**,
the pinned upstream KSU commit, and the `ksud` embedded module
hash against the audited GZIF-vermagic donor candidate.

It does **not** rerun builds or regressions, call ADB, execute
BOPE, insmod any module, change SELinux, or flash anything.

```bash
cd ~/Root-My-Galaxy-GZIF
git pull --ff-only origin port/s918n-gzif-android17
python3 tools/linux/assemble-gzif-rootchain-host-only.py
```

Expected local output if both previously reported build
directories are still present:

```text
~/rmg-firmware/gzif-rootchain-host-only/s918n-gzif-bope-ksud-candidate/
  READ_ME_FIRST.txt
  rootchain-manifest.json
  HOST_ONLY_NOT_FOR_DEVICE/
    payload.so
    mm-exec-factory
    stability-launcher-s918ngzif
    cve-2026-43499-root
    ksud-selected.WIP
```

The copies are deliberately **non-executable (mode 0600)**
and labeled **HOST_ONLY_NOT_FOR_DEVICE**. This is an
integrity/provenance snapshot, not a deployment script.
Running it does not produce a Samsung-compatible
kernel module or establish that the existing donor-derived
module can load. The manifest explicitly retains
`full_root_ready: false` and `deployable: false`.

**Status:** GitHub script added; no execution of the newly
assembled host-only tool has been observed on the owner's WSL
as of this note. Do not repeat successful device KASLR tests
to validate a packaging operation.

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
