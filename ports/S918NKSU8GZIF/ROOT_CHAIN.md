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

### GZIF-only bounded SELinux fallback (new source, NOT DEVICE-VALIDATED)

The source review identified a specific unbounded waiting failure
after a successful UMH temporary-root bootstrap: the original root
daemon waits indefinitely for a `late-load` request to complete the
SELinux restoration. To reduce this exposure, the **disposable
GZIF-controlled-build copy only** now supports a new
`gzif_root_helper_guard.py` source overlay.

It adds an **180-second** monotonic watchdog, forked as a distinct
userspace process when the root daemon starts. At the deadline,
the watchdog attempts to write `1` to
`/sys/fs/selinux/enforce`; the root daemon itself uses a bounded
`poll` wait to stop accepting new temporary-root socket requests,
unlink `/data/local/tmp/temp_su.sock`, and attempt the same
enforcing-state restoration. Socket setup errors make an immediate
restoration attempt. The accepted sockets remain blocking to
preserve the original helper's request protocol.

**This is not a guarantee:** the watchdog cannot run when the
kernel panics, both processes die, or the UMH bootstrap never
starts it. Requests already in progress may continue beyond the
acceptance deadline. Restoration during a long KernelSU load
can cause the load to fail. The separate BOPE kernel-memory
restoration and donor module admission risks are unchanged.

To compile **only** the changed helper, without repeating the
previously successful BOPE native build, Rust/Cargo or KASLR tests:

```bash
cd ~/Root-My-Galaxy-GZIF
git pull --ff-only origin port/s918n-gzif-android17
python3 tools/linux/build-gzif-fused-helper-only.py
```

The script reuses the owner-confirmed previous native build
report `s918ngzif-7cjfl28m`, copies the generated GZIF helper
into a new host-only workspace, applies the safety overlay
there (never in donor source), invokes **only the root helper
NDK compiler**, verifies resulting ARM64 ELF and marker
strings, then writes `build-report.json` and a source-overlay
report. Its output is not approved for a device root test.

For a new **host-only** five-file integrity snapshot with
the guarded helper replacing the old one, pass the generated
fused-helper `build-report.json` path, shown at build
completion, to:

```bash
python3 tools/linux/assemble-gzif-rootchain-host-only.py \
  --fused-helper-report /actual/s918ngzif-helper-fuse-.../build-report.json
```

The assembler chooses a new `-selinux-fuse` output folder
and rejects files whose original build hash/provenance
does not agree with the previous BOPE report. This
snapshot contains no deploy or exploit commands.

**Owner-confirmed 2026-10-15:** the guarded helper-only
NDK build **succeeded**, without rebuilding BOPE or ksud:

```text
[SOURCE] Copied previous GZIF helper to isolated host workspace
[GZIF] 180-second independent SELinux restoration fuse + socket expiry
[BUILD] Recompiling ONLY root helper (no BOPE/KSU/test reruns)
[BUILT] guarded root_helper: ELF64/AArch64 (29528 bytes)
Report: /home/ebrahim/rmg-firmware/gzif-helper-fuse-builds/s918ngzif-helper-fuse-njug65hu/build-report.json
Status: HOST_BUILT_FUSE_ONLY; root and device load NOT validated
```

The new binary is the 29,528-byte AArch64 GZIF root helper.
The owner can now create the **separate host-only guarded
five-file snapshot**, using the previously built four
other artifacts, without another compiler or device test:

```bash
python3 tools/linux/assemble-gzif-rootchain-host-only.py \
  --fused-helper-report \
  "$HOME/rmg-firmware/gzif-helper-fuse-builds/s918ngzif-helper-fuse-njug65hu/build-report.json"
```

**Still not device-validated:** temporary-root socket,
live watchdog execution, SELinux enforcing restoration
and KernelSU module acceptance. A 180-second userspace fuse
is best effort, not a kernel recovery mechanism. The
`HOST_ONLY_NOT_ROOT_READY` classification remains correct.

### SELinux restoration sequencing gap — source review

Source-level review after the completed five-file assembly found a
concrete sequencing hazard in the existing BOPE ↔ KernelSU chain:

1. `10_workqueue_umh_root.c:root_umh_install_fd_tracked()`
   writes a zero byte to the kernel enforcing-state address to
   permit the temporary UMH root bootstrap.
2. The `out:` cleanup block restores the original SELinux byte
   only under `if (!result && selinux_changed)`.
   **On a successful temporary-root socket result, it intentionally
   does not restore enforcing inside this function.**
3. `helper/su_daemon.c:run_kernelsu_late_load()` launches
   `ksud late-load`, checks KernelSU control and then calls
   `restore_selinux_enforcing()` after the child completes.
4. Therefore a successful temporary root that is **not followed
   by completion of the separate late-load request** lacks a
   demonstrated guarantee that SELinux enforcing is restored.
   The existence of a host-built `ksud-selected.WIP` does not
   close this lifetime/cleanup gap.

The original donor does contain best-effort failure cleanup,
but that does **not** prove fail-safe recovery on crash,
SIGKILL, system restart, rejected module or an absent
late-load request. This is a specific engineering **NO-GO**
for calling the full sequence reliable or deploying the
donor module just because the userspace files are now built.
A robust solution needs an independently verified bounded
restoration mechanism and Samsung-compatible module admission,
rather than another KASLR, build or stability test.

### Owner-confirmed five-artifact off-device assembly — 2026-10-15

The owner successfully ran
`python3 tools/linux/assemble-gzif-rootchain-host-only.py`
following the fast-forward Git pull to `9452402`. Its exact
reported completion was:

```text
[ASSEMBLED] 5 Android ARM64 host artifacts: /home/ebrahim/rmg-firmware/gzif-rootchain-host-only/s918n-gzif-bope-ksud-candidate
Manifest: /home/ebrahim/rmg-firmware/gzif-rootchain-host-only/s918n-gzif-bope-ksud-candidate/rootchain-manifest.json
Status: HOST_ONLY_NOT_ROOT_READY; no device actions
```

This assembly reuses all **five previously built ARM64 binaries**,
validates the original reported SHA-256 and sizes, and places
copies in a non-executable host-only directory. It does not
start a root session, trigger BOPE kernel mutation, load the
unsigned ZZI8-derived KernelSU module, or flash Android.

**Completed work (do not repeat without cause):**
12/12 host regression suite; on-device guarded two-page KASLR
quorum with TraceFS restored `0/0`; BOPE four-artifact
host build; Rust/Cargo `ksud` host build; five-artifact
hash-verified host-only assembly.

**Actual outstanding root work (not a request for more tests):**
Samsung GZIF-specific futex/allocator and memory-write
runtime behavior, temporary root/UMH completion and
restoration, module admission on the Samsung kernel,
the KernelSU control handshake, and SELinux enforcing
recovery. The donor module has a GZIF-matching vermagic
field only; it is not a source-rebuilt or device-accepted
kernel module. `full_root_ready=false`; no device
deployment is approved by successful assembly.

### Owner-confirmed fused five-artifact assembly — 2026-10-15

After the 29,528-byte GZIF SELinux-fused root-helper build,
the owner ran the optional host-only assembly with its report:

```text
[ASSEMBLED] 5 Android ARM64 host artifacts: /home/ebrahim/rmg-firmware/gzif-rootchain-host-only/s918n-gzif-bope-ksud-candidate-selinux-fuse
Manifest: /home/ebrahim/rmg-firmware/gzif-rootchain-host-only/s918n-gzif-bope-ksud-candidate-selinux-fuse/rootchain-manifest.json
Status: HOST_ONLY_NOT_ROOT_READY; no device actions
```

**This milestone is complete.** The separately labeled snapshot
contains four original BOPE/launcher/factory/ksud artifacts and
the **fused GZIF-specific root helper instead of the old helper**.
The assembler verified original binary hashes, KMI/loader
strings, the fused-helper build-report linkage, and the embedded
donor-module's audit identity. No file was deployed to Android.

No repeated KASLR, 12/12 tests, helper/BOPE/ksud rebuild, or
re-assembly is needed. The actual blocker is **kernel execution
and KernelSU module admission**, not host artifact availability.

### KernelSU module admission — exact unresolved gate

The owner-read SM-S918N GZIF `/proc/config.gz` contained
`CONFIG_MODULES=y`, `CONFIG_MODVERSIONS=y`,
`CONFIG_MODULE_SIG=y`, `CONFIG_MODULE_SIG_PROTECT=y`
and `CONFIG_MODULE_SIG_ALL=y`, with
`CONFIG_MODULE_SIG_FORCE` disabled. These facts alone
**neither guarantee nor categorically deny unsigned
third-party module admission**.

Android GKI's `CONFIG_MODULE_SIG_PROTECT` protects
certain **symbol accesses and exports**. For an unsigned
unprotected module, policy can reject disallowed symbols with
`-EACCES`; it is not equivalent to a blanket mandate
that every vendor module have a Samsung signing key.
Official references:

- [Android common kernel MODULE_SIG_PROTECT Kconfig](https://android.googlesource.com/kernel/common/+/1694e2760e48d82ce4cc30a196d93fef6ae1f69d/kernel/module/Kconfig)
- [AOSP kernel modules overview](https://source.android.com/docs/core/architecture/kernel/modules)
- [GKI module symbol protection behavior](https://android.googlesource.com/kernel/common/+/e9669eeb2f4580e44226cf1b582340f4b6388387%5E%21/)

The candidate's **139 matched modversion CRCs**, symbol presence
and matching donor-vs-GZIF BTF subset are **not** a proof that
the required symbols are allowed for an unsigned module or that
its runtime structure layout is fully compatible. A
`vermagic` replacement is **not** a source build.
The live `/proc/sys/kernel/modules_disabled` state
could not be read under unprivileged ADB; it remains unknown.

**Next concrete dependency:** obtain a reproducible *matching*
GZIF kernel build/Kbuild and a trusted source-built
KernelSU v3.4.0 `.ko`, or an independently documented
admission-compatible KMI module with the necessary symbol
access under this exact running kernel. The original ZZI8
binary is insufficient proof. Samsung's
[Open Source Release Center](https://opensource.samsung.com/)
is an appropriate place to request/search for SM-S918N
source, but no exact GZIF source archive and accompanying
matching `Module.symvers`/prepared artifacts have been
verified in this project. The fact that Samsung publishes
GPL source does **not** imply it supplies its exact private
production kernel build tree, signing keys or module
admission policy.

**Device/root status stays NO-GO:** the one-shot
`GZIF_KASLR_ONLY` demonstration does not validate
the donor-inherited futex/kernel-RW exploit or the
`root_umh_install_fd_tracked` recovery path. The new
180-second userspace fuse cannot restore kernel memory
after a panic or guarantee the module can load. There
is no documented successful root or persistent KernelSU
on SM-S918N/GZIF as of this owner session.

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

## Owner-confirmed device state and next guard delta — 2026-10-15

The owner copied the five existing GZIF snapshot artifacts to Android
using WSL/ADB and confirmed **5/5 local-vs-device SHA-256 matches**.
A non-root read-only ADB check reported the expected GZIF kernel
release, SELinux `Enforcing`, **no loaded KernelSU module** and no
`/data/local/tmp/temp_su.sock`. Running the installed `ksud`
binary's `--version` returned `ksud 3.4.0 (uapi: 4)` with exit 0.
This proves userspace execution only, not kernel module admission or root.

Review of the disposable GZIF root-helper safety overlay identified a
further fail-open case: after successful bind/listen, it did not check
the return value of `chmod(BOOTSTRAP_SOCK_PATH, 0666)`. If chmod failed,
the client might be unable to connect while the temporary-root daemon
waited for the full fuse duration. The host-source overlay now aborts
that path by closing and unlinking the listener and immediately
**attempting** restoration of SELinux Enforcing. A narrow source-only
regression was added at
`tools/bope/tests/test_gzif_root_helper_guard.py`.

This is **new source, not a rebuilt or tested Android binary**.
The already transferred device helper has not been updated by the
GitHub change. New unit tests have been authored, not yet executed
on the owner's WSL. All previously completed build, 12/12 regression,
KASLR and hash-verification work is still valid and not repeated.

**Owner's first new guard regression run:** `1/5` tests passed; the other
`4/5` failed before build because the new `chmod` transformation removed
the literal source anchor expected by the older bind/listen cleanup
transformation. Commit `37957836` moved the chmod transformation **after**
bind/listen cleanup in the GZIF overlay. Source-pattern verification
confirmed both replacements retain distinct anchors in the original
donor; the corrected Python regression and helper NDK rebuild were then
rerun successfully on owner's WSL. No Android operation occurred during the failed run.

**Owner-confirmed corrected GZIF helper guard (2026-10-15):** the
dedicated five new source-only regression tests completed with `OK`,
and recompilation of **only** the root helper succeeded:

```text
[SOURCE] Copied previous GZIF helper to isolated host workspace
[GZIF] 180-second independent SELinux restoration fuse + socket expiry
[BUILD] Recompiling ONLY root helper (no BOPE/KSU/test reruns)
[BUILT] guarded root_helper: ELF64/AArch64 (29592 bytes)
Report: /home/ebrahim/rmg-firmware/gzif-helper-fuse-builds/s918ngzif-helper-fuse-b34owbef/build-report.json
Status: HOST_BUILT_FUSE_ONLY; root and device load NOT validated
```

The **29,592-byte** helper supersedes the previous **29,528-byte**
GZIF guard build for new host-source analysis. It adds fail-closed
cleanup when `chmod` of the temporary-root listener fails and retains
the existing 180-second watchdog and bind/listen failure cleanup.
This new helper has **not been assembled into a new five-file bundle**
or installed on Android. The previously hash-verified five-file
device snapshot and previous host-only assembly remain **older binary
versions**. Running these new tests does not validate kernel mutation,
SELinux recovery on device or Samsung KernelSU module admission.

**NO-GO remains:** no proof of kernel state recovery after futex/FOPS
mutation, UMH timeout, usermode helper crash, or kernel panic.
Socket recovery does not ensure module acceptance, KernelSU handoff
or SELinux restoration if BOPE fails before the root daemon starts.
The exact donor-derived module is still not a GZIF source-built LKM,
even though the owner reports the developer believes it compatible.

## 2026-10-15: concrete FOPS/futex recovery gate (host source only)

A conservative read-only audit was added as
`tools/linux/audit_gzif_kernel_recovery.py`. It reports
`NO_GO_KERNEL_RECOVERY_UNPROVEN` with exit code **2**, not a
successful root-ready state. It checks exact donor source anchors
and rejects unknown source changes instead of assuming recovery.

The **four current blockers** are:

- `FOPS_FALLBACK_LOG_ONLY`: `recover_ashmem_fops()` only logs
  `fops-recovery-reboot-required`; it has no demonstrated alternate writer.
- `PIPE_INSTALL_FAILURE_AFTER_MUTATION`: failure in `oss_pipe_rw_install()`
  returns without a proven way to restore mutated FOPS.
- `UMH_TIMEOUT_STATIC_PATH_PINNED`: a pending timed-out UMH trigger
  causes cleanup to skip restoring the static usermode-helper path.
- `SELINUX_SUCCESS_LIFETIME_GAP`: successful temporary-root socket
  creation leaves restoring enforcing to later userspace work.

An existing FOPS pipe readback guard and denial of unsafe retries
are partial mitigations. Neither proves kernel recovery.

Separately, the disposable GZIF-only helper overlay now **attempts**
SELinux restoration when UMH argument validation, credential setup,
daemon fork or setsid fails before starting the userspace watchdog.
This is a narrow cleanup improvement; SIGKILL, kernel panic, unsafe
FOPS state and module admission are still unresolved.

New tests: `tools/bope/tests/test_gzif_kernel_recovery_audit.py`
(3 cases) and two additional cases in
`tools/bope/tests/test_gzif_root_helper_guard.py`.
These changes have not been owner-run, rebuilt or deployed. The
existing 29,592-byte WSL helper and older on-device helper are unchanged.

Host-only validation (the audit's exit 2 is the expected NO-GO):

```bash
cd ~/Root-My-Galaxy-GZIF
git pull --ff-only origin port/s918n-gzif-android17
python3 -m unittest tools.bope.tests.test_gzif_root_helper_guard tools.bope.tests.test_gzif_kernel_recovery_audit -v
if python3 tools/linux/audit_gzif_kernel_recovery.py; then
  echo "Unexpected audit exit 0; manual review required"
else
  echo "Recovery audit exit code (expected 2): $?"
fi
```

Once only the new tests pass, if a new helper artifact is wanted,
`python3 tools/linux/build-gzif-fused-helper-only.py` recompiles
**only** that changed helper off-device. Do not deploy it merely
because the audit or NDK build completed.
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
