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


## Physical device identity preflight — 2026-10-15

**Read-only verification completed, as reported from Windows PowerShell**:

- `Device identity: IDENTITY_MATCH`
- `SELinux: Enforcing (read-only)`
- Script: `tools/windows/verify-s918n-gzif.ps1`
- Input: the exact `SM-S918N / S918NKSU8GZIF` identity described below
- Evidence scope: user-provided console output; the full local JSON report
  has **not** been uploaded
- No device serial number or other user-identifying details recorded here

This checkpoint confirms **runtime identity only** and must not be interpreted
as an exploit test, root success, stability validation, or authorization to
enable the firmware profile in the public Android app. The next environment
check is Windows `wsl --status` and `wsl -l -v`, followed by independent ELF /
kallsyms reconstruction before any BOPE build or target integration.

## Windows ADB preflight

On Windows, follow the read-only [PowerShell/ADB setup guide](../../tools/windows/README.md) and run the [SM-S918N GZIF identity check](../../tools/windows/verify-s918n-gzif.ps1) before attempting any device-side validation. This check does not root, modify, or flash the phone.

## Verified BTF ABI audit (completed offline)

The user-supplied boot was decompressed to an Android boot-v4 image; its kernel
release and embedded BTF were verified locally with `pahole`. The recorded
[ABI report](btf-abi-report.json) contains **74 of 74 resolved BTF values**:
63 structure-field offsets, 8 structure sizes and 3 enum values. Comparison
with the upstream ZZI8 donor `target.h` found **0 ABI differences**.

Reproduce this independently with:

```sh
python3 tools/bope-btf-audit /path/to/vmlinux-GZIF.btf \
  --donor-header targets/zzi8-WIP/brazilian-open-payload-engine/src/target.h \
  --output /tmp/gzif-btf-audit.json
```

This is **not** proof that the static symbol offsets are unchanged. The BOPE
port still requires a reliable target `kallsyms`, a symbolized `vmlinux.elf`,
cross-validation of generated `src/target.h` against ELF+BTF, KernelSU module
ABI verification, BOPE binary builds, and clean-boot physical-device trials.
**Do not copy ZZI8 symbol addresses into a GZIF executable based on the BTF
comparison.** Do not enable GZIF in the app target manifest without those gates.

## User-confirmed WSL2 offline extraction — 2026-10-15

The Windows/Ubuntu WSL2 operator independently confirmed the following from
the matching local GZIF boot image:

- `boot.img.lz4` checksum matched the previously recorded SHA-256;
  `boot.img` decompressed to 100663296 bytes.
- The unpacked kernel is 46860800 bytes with the **exact** GZIF release
  `5.15.197-android13-8-34343818-abS918NKSU8GZIF` and matching build date.
- An embedded 6098807-byte BTF blob was extracted and accepted by `pahole`.
- `tools/bope-btf-audit` reported `resolved_count=74`, `missing=[]`,
  `compared=74`, `matched=74`, `differences={}`.

This records user-reported terminal results, not uploaded or independently
reviewed logs. It only confirms structural compatibility; it does not
establish that BOPE static symbol offsets, KernelSU ABI or kernel exploit
calibration are valid.

### Offline kallsyms and ELF reconstruction (next validation gate)

In the repository checkout on Ubuntu under WSL2:

```bash
git pull --ff-only origin port/s918n-gzif-android17
source .venv/bin/activate
python3 -m pip install vmlinux-to-elf
sudo apt install -y binutils
bash tools/linux/recover-gzif-symbols.sh
```

The script verifies the supplied `boot.img.lz4` SHA-256 and extracted kernel
release, then invokes upstream `kallsyms-finder` and `vmlinux-to-elf` on
the **local** kernel with tool-inferred base address. It generates analysis
artifacts `kallsyms_GZIF.kallsyms` and `vmlinux_GZIF.elf` next to the
firmware, with separate logs. If recovery fails, inspect the logs and do not
copy donor symbol offsets as a substitute. Generated firmware binaries and
symbols are not uploaded to the repository or flashed to the phone.

## WSL2 GZIF symbol recovery — user-confirmed 2026-10-15

After resolving a Python 3.14 `Python.h` development-header dependency issue,
the owner ran `bash tools/linux/recover-gzif-symbols.sh` successfully:

- Boot SHA-256 and extracted GZIF kernel release matched the recorded values.
- `kallsyms_GZIF.kallsyms`: **126452** lines, approximately **5.4 MiB**.
- `vmlinux_GZIF.elf`: approximately **51 MiB**, passing the script's
  AArch64 ELF-machine check.
- Both outputs remain **offline in the owner's WSL2 firmware directory**.
  The files themselves, hashes, and full extraction logs have not been
  independently inspected or committed to GitHub.

**Recovery success is not proof that every recovered symbol address is valid.**
The next gate is to compare the target ELF's symbol addresses to kallsyms and
verify an independently regenerated firmware contract against ELF and BTF.
Use `--skip-build --skip-kernelsu` and a separate output root for the first
contract derivation; no app integration or device modification should occur.
See `tools/bope/README.md` for the standalone factory CLI entry point.

### ELF-to-kallsyms address cross-check — user-confirmed

The owner compared a sample of four recovered kernel addresses using
`llvm-nm -n` against the `kallsyms-finder` text output:

| symbol | ELF and kallsyms address |
| --- | --- |
| `_text` | `ffffffc008000000` |
| `worker_thread` | `ffffffc00810dd84` |
| `init_task` | `ffffffc00ac05400` |
| `selinux_state` | `ffffffc00ad8e600` |

All four *addresses* matched. Types for `init_task` and
`selinux_state` differ (`T` in reconstructed ELF versus `D`/`B` in
the native kallsyms dump); verify addresses using the full ELF/BTF
contract rather than relying on reconstructed ELF symbol types.

**Donor choice correction:** use `targets/zzi8-WIP` for both `--donor`
and `--engine-donor` on this GZIF port. The legacy `targets/zzhl`
header lacks `TARGET_KERNEL_VERSION`, which the current
`derive_contract` requires. Donor inheritance is limited to
calibration/configuration and must not be treated as proof of kernel
symbol offsets or a verified payload.

## GZIF generated firmware contract — owner-confirmed 2026-10-15

The owner ran the standalone `tools/bope-from-factory` pipeline locally in
WSL2 with `--donor targets/zzi8-WIP --engine-donor targets/zzi8-WIP`,
the exact fingerprint and kernel release, `--base-address
0xffffffc008000000`, and the intentionally restrictive flags
`--skip-build --skip-kernelsu`. The output was written **outside the Git
checkout**, under `~/rmg-firmware/gzif-contracts/s918ngzif-WIP`.

The resulting `port-manifest.json`, according to user-reported console
output, states:

- `status: GENERATED_WIP_DEVICE_VALIDATION_REQUIRED`
- `target.build: S918NKSU8GZIF`
- `contract.verification.passed: true`
- `len(contract.verification.checks): 107`
- `len(contract.changed_values): 23`
- `len(contract.inherited_calibration_values): 169`
- `contract.verification.errors: []`

The report and generated header have not been uploaded or independently
reviewed. Note that the manifest key `inherited_calibration_values` actually
holds **all inherited TARGET_* definitions**, not just device-calibrated
parameters. The next review must classify these inherited values, especially
futex timing, memory reclaim, KASLR, object geometry and pipe handling, and
cross-check the full generated `target.h` against the target firmware. Do not
construe successful consistency checks as a validated exploit, a safe
device-side test or a working KernelSU root port.

To repeat the contract verifier against the locally generated files:

```bash
T="$HOME/rmg-firmware/gzif-contracts/s918ngzif-WIP"
./tools/bope-verify-target \
  --header "$T/brazilian-open-payload-engine/src/target.h" \
  --elf "$T/firmware/vmlinux_S918NGZIF.elf" \
  --btf "$T/firmware/vmlinux_S918NGZIF.btf"
```

## Inherited-values triage — owner-confirmed 2026-10-15

The operator inspected the generated `port-manifest.json` and found 23
changed values: six firmware identity strings and seventeen symbol-derived
offsets. The inherited array has **169 `TARGET_*` macros** and is not
strictly a calibration-only list. Prefix-based counts observed:

| Category | Inherited entries |
| --- | ---: |
| Futex / timing | 43 |
| Memory / reclaim | 28 |
| Pipe / ConfigFS | 29 |
| KASLR / mapping | 8 |
| Fake objects / signal | 28 |
| Other inherited macros | 33 |

The generated `target.h` was checked for stale donor identity strings.
There were **no matches inside active macros**; the only match was a stale
top-of-file prose description mentioning `SM-S918B` and the old ZZI8
beta-release description. Commit
`90b0b9befb43411dd9acb077a5152a48494ca782`
corrected this for **future generated contracts** with
`normalize_firmware_contract_comment`. The owner's existing local
generated `target.h` retains its older comment until regeneration or an
explicit prose-only local edit.

**Gate remains blocked:** inherited runtime tunables and device calibration
must be reviewed independently. This audit is a classification of
unverified settings, not authorization to run a privilege-escalation
payload or proof of platform stability.

### The 33 other inherited macros — owner-reported, triaged

The owner enumerated all 33 inherited `TARGET_*` values outside the
previously reported category prefixes. Each was classified, not approved:

| Triage class | Count | Examples and evidence still needed |
| --- | ---: | --- |
| ABI geometry / fixed-looking constants | 10 | `TARGET_FILE_CACHE_SIZE`, `TARGET_RB_*_OFF`, `TARGET_PAGE_SIZE`, `TARGET_TTY_MAGIC`; cross-check independent target BTF and device kernel configuration |
| Runtime-specific values | 16 | `TARGET_TRACE_SCHED_BLOCKED_REASON_ID`, `TARGET_KERNEL_IMAGE_SPAN`, `TARGET_KMALLOC_4K_CACHE_NAME`, reclaimed-object live offsets; may be firmware/boot/calibration dependent |
| Bootstrap path, guard and timeouts | 7 | `TARGET_STATIC_UMH_*`, `TARGET_BINFMT_TRIGGER_PATH`, `TARGET_UMH_*`; structural string sizes are checkable offline but bootstrap behavior is **not** |

The added offline audit `tools/linux/audit-gzif-inherited.py` checks five
narrow invariants against the owner's **GZIF BTF** or source-provided static
guard: three `rb_node` offsets, UMH guard size and UMH path/patch-buffer
fit. It separately **reports but does not validate** the difference between
`sizeof(struct file)` and the inherited SLAB allocation size.
Five passes still **do not certify any inherited parameter for live use**.

```bash
cd ~/Root-My-Galaxy-GZIF
git pull --ff-only origin port/s918n-gzif-android17
source .venv/bin/activate
python3 tools/linux/audit-gzif-inherited.py
```

A local `inherited-offline-audit.json` is written beside the generated
manifest. Do not commit the owner's kernel binaries or generated exploit
artifacts. The script never contacts the device and never changes the
application support manifest.

### Correcting inherited FILE_CACHE_SIZE audit — 2026-10-15

The first owner-run `python3 tools/linux/audit-gzif-inherited.py` reported
`Offline structural checks: 5/6` with one failure:

```text
[FAIL] BTF struct file size: expected 264, header 320
```

**This was a false assumption in the offline auditor, not proof that the
contract was wrong.** BTF says `sizeof(struct file) = 264` bytes, but
the inherited `TARGET_FILE_CACHE_SIZE = 320` is passed as a *SLAB
allocation/cache size* to `slab_cache_guard_begin`, which is not
required to equal the type size. Moreover, that code path is currently
`#if 0` disabled in the donor `09_pipe_buffer_rw.c`; do not enable it
or modify this constant merely to make the test pass.

The auditor was corrected in commit
`10a9eb3e75910a0d24b171d7083b10ba9e1f51c4`
to retain an explicit `UNVERIFIED_SLAB_OBJECT_SIZE` observation
and perform **five**, not six, separate structural checks:
three `rb_node` field offsets, guard byte count, and path/patch size
bounds. This deliberately **does not** validate the 320-byte cache
size. Three regression cases were added for the observation semantics.

The owner should pull the revised script, run
`python3 -m unittest tools.bope.tests.test_inherited_cache_observation -v`,
and re-run `python3 tools/linux/audit-gzif-inherited.py`.
A clean `5/5` only confirms those five structural invariants and does
not enable device execution or support.

### Owner-confirmed corrected inherited audit — 2026-10-15

With commit `c2fae0d601f8be21f757c3b10999336df6b4895e`
checked out in Ubuntu WSL2, the owner reported:

- `python3 -m unittest tools.bope.tests.test_inherited_cache_observation -v`:
  **3 passed**.
- `python3 tools/linux/audit-gzif-inherited.py`:
  **5/5 offline structural checks passed**.
- `TARGET_FILE_CACHE_SIZE` remains explicitly
  **UNVERIFIED_SLAB_OBJECT_SIZE**: inherited cache size 320 versus
  `sizeof(struct file) = 264` from BTF. Those are different quantities,
  and the current donor's reference to this macro is under `#if 0`.
- Report remains local at
  `~/rmg-firmware/gzif-contracts/s918ngzif-WIP/inherited-offline-audit.json`.

**No device execution, root access, or build was performed.**

One additional live-runtime inheritance still blocks deployment:
`TARGET_TRACE_SCHED_BLOCKED_REASON_ID = 108` is a ZZI8 donor value,
not an independently checked GZIF trace event ID. The BOPE tracefs
KASLR resolver in `01_kernel_base_tracefs.c` **writes** tracing state
(`tracing_on` and `sched_blocked_reason/enable`) and must not be run
just to discover this ID. A non-root, read-only ADB probe may attempt to
read the kernel's `/sys/kernel/tracing/events/sched/sched_blocked_reason/id`.
If access is denied or the file is absent, record it as **UNAVAILABLE**;
do not use `su`, change SELinux, remount tracefs, or assume 108. Even
an ID match alone would not validate the KASLR leak, slide geometry,
memory reclamation, or root payload.

### Read-only on-device tracepoint ID verified — 2026-10-15

The owner ran the following command in Windows PowerShell with the device
connected over normal (non-root) ADB:

```powershell
$adb = "C:\\Android\\platform-tools\\adb.exe"
& $adb shell cat /sys/kernel/tracing/events/sched/sched_blocked_reason/id
```

The phone returned **`108`**, matching the inherited
`TARGET_TRACE_SCHED_BLOCKED_REASON_ID = 108U` from ZZI8. This
is **user-reported runtime evidence** that the event ID exists and
matches on the running SM-S918N GZIF kernel. The ADB daemon started
normally; starting the ADB daemon is not a change to the phone's
trace configuration.

**Scope of confirmation:** the ID alone. It does not verify the
tracepoint event field format, the raw ring-buffer record layout,
the `caller` offset, the KASLR slide, access to trace pipes, or
whether BOPE's KASLR routine works on this device. No trace event was
enabled or captured. For the next read-only check, use:
`adb shell cat /sys/kernel/tracing/events/sched/sched_blocked_reason/format`;
do **not** run the donor KASLR resolver, which writes to tracefs.

### Read-only tracepoint field layout confirmed — 2026-10-15

The owner then read the live device's tracepoint format via non-root ADB:

```powershell
& $adb shell cat /sys/kernel/tracing/events/sched/sched_blocked_reason/format
```

The returned event metadata contained:

| Field | Byte offset | Size |
| --- | ---: | ---: |
| `common_type` | 0 | 2 |
| `common_flags` | 2 | 1 |
| `common_preempt_count` | 3 | 1 |
| `common_pid` | 4 | 4 |
| `pid` | 8 | 4 |
| `caller` | 16 | 8 |
| `io_wait` | 24 | 1 |

It reported `ID: 108`, consistent with the separately read event ID.
In the donor `01_kernel_base_tracefs.c`,
`TARGET_TRACE_CALLER_OFF = 0x10` and
`TARGET_TRACE_SCHED_BLOCKED_REASON_ID = 108` therefore match the
**individual tracepoint payload format** on GZIF. A 24-byte prefix is
sufficient to reach the end of `caller`, but the event has an additional
`io_wait` field at offset 24, so
`TARGET_TRACE_LOOSE_RECORD_SIZE = 0x18` must **not** be interpreted as
the complete event record size.

This does **not** validate the raw per-CPU trace ring buffer page format,
event record framing/alignment, `TARGET_TRACE_TYPE_LEN_MASK`, trace
reader access, KASLR slide inference, or privilege escalation.
Next safe read-only metadata inputs are:
`/sys/kernel/tracing/events/header_page` and
`/sys/kernel/tracing/events/header_event`.
Neither requires enabling tracing; if denied, leave these properties
unverified. Do not run the KASLR resolver as a format test because it
writes tracefs state.

### Read-only ring buffer page metadata — owner-confirmed 2026-10-15

The owner successfully read
`/sys/kernel/tracing/events/header_page` over non-root ADB, which returned:

```text
field: u64 timestamp;   offset:0;  size:8;
field: local_t commit;  offset:8;  size:8;
field: int overwrite;   offset:8;  size:1;
field: char data;       offset:16; size:4080;
```

Thus the tracefs metadata describes a **4096-byte page** with its
`commit` value at offset 8 and data starting at offset 16. The donor
`parse_trace_page` implementation reads `commit` at offset 8,
starts structured record parsing at offset 16, uses
`TARGET_PAGE_SIZE = 0x1000`, and bounds the declared data extent by
the actual read length. Those **page-level assumptions agree** with
the reported metadata. This does not independently establish
the contents of the commit bitfields or the raw event record encoding.

A separate attempt to read
`/sys/kernel/tracing/events/header_event` returned
**`Permission denied`**. This is an **unavailable** verification gate,
not an error to bypass. In particular the raw ring-buffer per-event
record encoding, the `TARGET_TRACE_TYPE_LEN_MASK = 0x1f`
framing behavior, actual trace ring reader access and KASLR
candidate extraction **remain unverified**. Do not escalate
privileges, change access controls, enable tracing, or run
the KASLR resolver to bypass this limitation.

The device has not been rooted or modified during these
read-only metadata checks.

## Offline KernelSU donor inspection — owner-confirmed 2026-10-15

The owner inspected the **unmodified** ZZI8 KernelSU Next v3.4.0 module
`targets/zzi8-WIP/kernelsu-next/out/kernelsu-next-zzi8-v3.4.0/android13-5.15_kernelsu.ko`
on Ubuntu WSL2. Reported ELF details:

- Architecture: **ELF64 / AArch64**.
- Module name: `kernelsu`; `depends=` empty.
- Donor `vermagic`:
  `5.15.197-android13-8-34343818-abS918BXXUAZZI8 SMP preempt mod_unload modversions aarch64`.
- Exact GZIF required kernel release:
  `5.15.197-android13-8-34343818-abS918NKSU8GZIF`.

**Vermagic does not match GZIF.** The module must never be loaded onto the
GZIF phone in its current form, and modifying vermagic does not itself
establish kernel ABI compatibility or license a device load.

A new read-only static auditor invokes the existing module compatibility
checks against the locally generated GZIF symbolized ELF, kallsyms and
BTF, comparing exported CRCs, undefined symbols, eight BTF structure
layouts, and `struct module` relocation offsets. It inspects the
**unchanged donor module**: it intentionally does not retarget its
vermagic, build a new binary or touch Android.

```bash
cd ~/Root-My-Galaxy-GZIF
git pull --ff-only origin port/s918n-gzif-android17
source .venv/bin/activate
sudo apt install -y kmod
python3 tools/linux/audit-gzif-kernelsu-static.py
```

The output is stored only under the owner's local WIP target at
`~/rmg-firmware/gzif-contracts/s918ngzif-WIP/kernelsu-donor-static-audit.json`.
The overall compatibility result is expected to be `false` for this
**original donor** because its vermagic is unchanged. The other comparison
results are useful diagnostics; they are not a build or device-root gate.
Any mismatch or incomplete audit remains a blocker.

### KernelSU donor ABI audit — owner-confirmed 2026-10-15

The owner ran `python3 tools/linux/audit-gzif-kernelsu-static.py` in WSL2
against the original ZZI8 module and **GZIF's reconstructed kernel**.
The local script reported:

| Diagnostic | Result |
| --- | --- |
| Donor module SHA-256 | MATCH |
| Module architecture | ELF64 / AArch64 (previous readelf) |
| Undefined symbols | 203 |
| Symbols not found in GZIF kallsyms | 0 |
| Module CRC entries | 139 |
| Entries matched to reconstructed GZIF kernel CRCs | 139 |
| CRC mismatches | 0 |
| Missing target CRCs | 0 |
| BTF layout mismatches | 0 |
| `struct module` relocation mismatches | 0 |
| Target vermagic match | **False** (unchanged ZZI8 original) |
| Overall `passed` | **False**, as expected |

The layout comparison uses **donor kernel BTF** instead of the original
module's own DWARF, so it is conditional evidence rather than an
independent validation of the module build configuration. The kernel
ELF itself was reconstructed from firmware and must not be conflated
with a compiler-produced symbolized `vmlinux`.
The audit report was generated locally, not independently retrieved.

A separate analysis-only helper
`tools/linux/check-gzif-ksu-retarget.py` requires the verified donor
hash and pre-retarget audit, then writes a **local WIP copy** with only
the same-length `vermagic` release text changed, re-runs the complete
host static ABI checks, and records a report. No module is compiled,
signed, uploaded, insmod'ed, installed or flashed.

```bash
cd ~/Root-My-Galaxy-GZIF
git pull --ff-only origin port/s918n-gzif-android17
source .venv/bin/activate
python3 -m unittest tools.bope.tests.test_ksu_metadata_retarget -v
python3 tools/linux/check-gzif-ksu-retarget.py
```

Outputs stay outside the Git checkout:
`~/rmg-firmware/gzif-contracts/s918ngzif-WIP/analysis-only/`.
**Even if the modified metadata makes every static check pass, the
candidate remains NOT DEVICE-VALIDATED and MUST NOT BE LOADED.**
Further blockers include Samsung module signing/loading policy,
device-dependent BOPE reclaim/timing, trace ring framing access,
KernelSU behavior, and clean-boot safety.

### Owner-confirmed metadata-only KernelSU WIP audit — 2026-10-15

Following a `git pull --ff-only`, the owner ran
`python3 -m unittest tools.bope.tests.test_ksu_metadata_retarget -v`
and `python3 tools/linux/check-gzif-ksu-retarget.py` in WSL2:

- **3/3 unit tests passed**, including missing/duplicate vermagic rejection.
- Original ZZI8 KernelSU module SHA-256: **MATCH**.
- Only the equal-length release in `vermagic` was changed in an
  **analysis-only local copy**.
- GZIF target vermagic: **True**.
- Missing undefined symbols: **0**; CRC mismatches: **0**;
  target CRC entries missing: **0**; BTF layout mismatches: **0**;
  `struct module` relocation mismatches: **0**.
- Host-side `Static audit passed: True`.
- Generated local artifact:
  `~/rmg-firmware/gzif-contracts/s918ngzif-WIP/analysis-only/kernelsu-gzif-vermagic-WIP.ko`.
- Generated report:
  `~/rmg-firmware/gzif-contracts/s918ngzif-WIP/analysis-only/kernelsu-gzif-metadata-static-audit.json`.

**Scope:** user-reported local host analysis, not uploaded binaries
or independently reproduced execution. The original ZZI8 module is
unchanged, and the WIP copy was **not** compiled for GZIF or installed,
signed, loaded, or executed on Android. Metadata retargeting plus a
positive ABI/CRC static report is **not** a proof of successful or safe
KernelSU operation.

**Open independent gates:** GZIF kernel module-loading configuration,
signature enforcement, actual `struct module` build evidence (donor BTF
was used in place of module DWARF), device runtime behavior, Samsung
security policies, BOPE timing/reclaim calibration, and safe clean-boot
validation. The app target must remain disabled. Before any attempt
at on-device loading, perform non-root, read-only checks of
`/proc/sys/kernel/modules_disabled` and
`/sys/module/module/parameters/sig_enforce` on the matching phone.
A missing/inaccessible file should be recorded as unavailable, never
bypassed. The values alone do not authorize module loading.

### Read-only module-loader policy preflight — owner-reported 2026-10-15

Windows ADB shell output from the matching SM-S918N / GZIF phone:

| Read-only check | Result | Interpretation |
| --- | --- | --- |
| `cat /proc/sys/kernel/modules_disabled` | `Permission denied` | The **runtime** modules-disabled state is **UNKNOWN**; do not attempt to bypass access controls |
| `cat /sys/module/module/parameters/sig_enforce` | `No such file or directory` | This path is **unavailable**; it does **not** establish that module signatures are optional |
| `ls -l /proc/config.gz` | `-r--r--r-- 1 root root 42167 ... /proc/config.gz` | Kernel build configuration is visible without root; a **read-only** copy can be audited |

Only the reported terminal output was reviewed, not a downloaded
kernel config. The next bounded check is to **read/copy** `/proc/config.gz`
with `adb pull` (if permitted) and inspect
`CONFIG_MODULES`, `CONFIG_MODVERSIONS`, `CONFIG_MODULE_SIG*`,
`CONFIG_MODULE_UNLOAD`, plus related module-loading security options.
Keep `modules_disabled` unknown even if static Kconfig values look
permissive: compile-time options do not settle runtime lockout or
Samsung signature/LSM enforcement.

Do not write sysctl or sysfs settings; do not alter SELinux,
attempt `su`, perform `insmod`, or treat static checks as device
load authorization. The analysis-only WIP module stays off-device.

### Owner-read GZIF build configuration — 2026-10-15

The owner successfully copied `/proc/config.gz` from the live SM-S918N
with **non-root ADB pull** (42,167 compressed bytes) and decompressed it
locally in Windows PowerShell. Selected Kconfig lines:

```text
CONFIG_IKCONFIG=y
CONFIG_IKCONFIG_PROC=y
CONFIG_MODULES_USE_ELF_RELA=y
CONFIG_MODULE_SIG_FORMAT=y
CONFIG_MODULES=y
CONFIG_MODULE_UNLOAD=y
CONFIG_MODVERSIONS=y
CONFIG_MODULE_SIG=y
# CONFIG_MODULE_SIG_FORCE is not set
CONFIG_MODULE_SIG_PROTECT=y
CONFIG_MODULE_SIG_ALL=y
CONFIG_MODULE_SIG_SHA1=y
CONFIG_MODULE_SIG_HASH="sha1"
CONFIG_MODULE_COMPRESS_NONE=y
CONFIG_MODULES_TREE_LOOKUP=y
# CONFIG_SECURITY_LOCKDOWN_LSM is not set
CONFIG_MODULE_SIG_KEY="certs/signing_key.pem"
CONFIG_MODULE_SIG_KEY_TYPE_RSA=y
```

These are **compile-time** settings, not evidence that this device permits
arbitrary third-party module loading. The original `modules_disabled`
runtime sysctl was inaccessible (`Permission denied`).

**Precise meaning of `CONFIG_MODULE_SIG_PROTECT`:** in the Android GKI
kernel Kconfig it enables restrictions on modules' use of GKI-protected
symbols and duplicate exports. It does **not** simply mean that every
module must have a trusted signature. Android's corresponding
`kernel/module/signing.c` conditionally omits the ordinary
`sig_enforce` sysfs parameter when this option is enabled, so its
absence is unsurprising and is **not** proof that signature or symbol
checks are disabled. Source references:

- https://android.googlesource.com/kernel/common/+/1694e2760e48d82ce4cc30a196d93fef6ae1f69d/kernel/module/Kconfig
- https://android.googleid.googlesource.com/kernel/common-patches/+/ee89e4d2634a5e1b31ed97b8cb1c85d5c196ea78/android-mainline/ANDROID-GKI-Add-script-to-generate-symbol-protection-headers.patch

Those are Android GKI source references, **not** proof of the exact Samsung
GZIF implementation or its protected-symbol lists. This distinction
matters despite the 139/139 CRC matches and clean eight-structure BTF
comparison. `MODULE_SIG_ALL=y` sets default build-time module signing
behavior, not permission to load a modified, unsigned module.
`MODULE_SIG_FORCE` is unset, but GKI symbol protection and Samsung
runtime policy still require separate validation.

The analysis-only `kernelsu-gzif-vermagic-WIP.ko` must remain **off-device**.
Next safe investigation is host-side module-signature metadata inspection
(`modinfo -F signer/sig_id/sig_key/sig_hashalgo`) on the
unchanged donor and local WIP copy. No `insmod`, module signing,
privilege escalation or changes to kernel policy.

### Owner-read KernelSU signature metadata — 2026-10-15

The owner used Ubuntu WSL2 `modinfo -F` to inspect the **original ZZI8
module** and the separately generated **GZIF vermagic-only WIP copy**.
Both files yielded empty `signer`, `sig_id`, `sig_key` and
`sig_hashalgo` fields. The `vermagic` line alone differed:

| Artifact | Kernel release in `vermagic` | Signature fields |
| --- | --- | --- |
| Unmodified donor | `5.15.197-android13-8-34343818-abS918BXXUAZZI8` | all empty |
| Local metadata-only WIP | `5.15.197-android13-8-34343818-abS918NKSU8GZIF` | all empty |

This is consistent with **no recognizable Linux module appended
signature** in either file. Absence of `modinfo` fields does not
demonstrate that the GZIF kernel would accept the module, nor exclude
separate vendor signing or symbol-protection policy. In particular
`CONFIG_MODULE_SIG_FORCE` being unset at build time is **not** a
module-loading authorization, and `CONFIG_MODULE_SIG_PROTECT=y` remains
an independent GKI protected-symbol concern. The runtime
`modules_disabled` value is unavailable to the non-root user.

For a second *strictly host-side*, non-modifying signature-format check,
compare the final bytes of each .ko with the standard Linux module
signature trailer `~Module signature appended~\n`. Do not infer
device loadability from this check. The GZIF WIP file must remain in
the `analysis-only` directory and **must not be insmod'ed, signed,
deployed, flashed, or presented as a working KernelSU port**.

## GZIF first isolated Android build — 2026-10-15

After the owner agreed to proceed with a backup and accepted test risks,
the work moved from individual ABI checks to producing the first **Android
NDK-compiled WIP binaries**. The added host-only
`tools/linux/build-gzif-android-wip.py` requires:

- The existing owner-generated, ELF/BTF-verified
  `~/rmg-firmware/gzif-contracts/s918ngzif-WIP` manifest/contract
- All five exact SM-S918N / GZIF identity macros
- Android NDK (tested path expected:
  `~/Android/Sdk/ndk/28.2.13676358` with API-35 Clang)
- Ubuntu `make` and `readelf`

Run on **Ubuntu WSL2**, without ADB or a device connection:

```bash
cd ~/Root-My-Galaxy-GZIF
git pull --ff-only origin port/s918n-gzif-android17
source .venv/bin/activate
python3 tools/linux/build-gzif-android-wip.py
```

If the NDK is missing, the script fails before any build and prints the
required compiler path. An installed NDK elsewhere can be passed as
`--ndk /path/to/android-ndk`. It never downloads tools or changes
the system setup.

The script **copies** the generated GZIF engine/helper and shared
`native/` and `stability-launcher/` source trees into a new isolated
`~/rmg-firmware/gzif-android-builds/s918ngzif-*/` workspace. It
builds `payload.so`, the mm-exec factory, stability launcher and root
helper, runs existing three host regressions, and checks the outputs
are ELF64/AArch64 before writing a local `build-report.json`.
It retains full build logs for failures.

**A successful compile is not a device test.** No file is copied into
the repository, Android app or phone, and the KernelSU module is not
loaded. All inherited futex timing, reclaim behavior, trace ring
framing, GKI security policy, and runtime stability gates remain open.
Do not deploy or execute any WIP binary while the on-device test
protocol and recovery plan are incomplete.

### Build gate correction: multiline identity macros — 2026-10-15

The owner first ran `python3 tools/linux/build-gzif-android-wip.py`
and received `[ERROR] Generated target.h does not match TARGET_KERNEL_RELEASE`
**before Android NDK compilation began**.

Root cause: the new builder's initial identity regex required
`#define TARGET_KERNEL_RELEASE "…"` on a single line, while the
upstream ZZI8 donor's `TARGET_KERNEL_RELEASE` (and fingerprint)
are defined as `#define TARGET_KERNEL_RELEASE \\` followed
by an indented quoted value on the next line. The contract generator
deliberately retains that correct C-preprocessor spelling.

Fixed in `tools/linux/build-gzif-android-wip.py` by strict
single-/two-line parsing with exact value checking, duplicate rejection
and CRLF support. Added seven host-only regression tests in
`tools/bope/tests/test_gzif_build_identity_parser.py`.
The generated GZIF header, manifest, firmware and Android device
were **not changed** by the fix.

Run:

```bash
cd ~/Root-My-Galaxy-GZIF
git pull --ff-only origin port/s918n-gzif-android17
python3 -m unittest tools.bope.tests.test_gzif_build_identity_parser -v
python3 tools/linux/build-gzif-android-wip.py
```

This is only a local WIP Android build. A successful build is still
**not** exploit validation or permission to run, load or flash it.

### Owner-confirmed on-device native smoke — 2026-10-15

The owner compiled the **separate read-only diagnostic**
`tools/android/gzif-device-smoke.c` using the Android NDK,
then ran `/data/local/tmp/gzif-device-smoke` from normal ADB shell
on the actual SM-S918N running GZIF. Its reported output was:

```text
GZIF_NATIVE_SMOKE_V1
Mode: read-only native Android process; no exploit invoked
Architecture: MATCH
Kernel release: MATCH
Kernel version: MATCH
ro.product.model: MATCH
ro.product.device: MATCH
ro.build.version.incremental: MATCH
ro.build.fingerprint: MATCH
SELinux: Enforcing
Execution UID: 2000
GZIF_NATIVE_SMOKE_RESULT: PASS
```

This is the **first user-reported successful execution of a
new GZIF-specific native binary on the physical device**. Exact kernel
release and version, model, device, incremental build and
fingerprint matched, with SELinux still enforcing and the process
running as the ordinary ADB shell UID 2000.

**Scope limitation:** this diagnostic does *not* contain or invoke BOPE,
tracefs writing, kernel heap reclaim, kernel R/W, KernelSU,
module loading or rooting. It is not an exploit success,
device-wide stability check or root authorization.
The separately built `payload.so`, helper, launcher and
metadata-retargeted unsigned KernelSU .ko remain **WIP/off-device**.

The owner's console output was reviewed; no private device
identifiers, firmware blobs or device logs were uploaded.
Whether the temporary diagnostic was removed after execution
has not been independently confirmed.

### Owner-reported live TraceFS access preflight — 2026-10-15

From Windows PowerShell over non-root ADB, the owner used shell
`-e`, `-r` and `-w` tests for the three tracefs paths needed
by the ZZI8 BOPE KASLR resolver:

| TraceFS path | Readable | Writable |
| --- | --- | --- |
| `/sys/kernel/tracing/tracing_on` | yes | yes |
| `/sys/kernel/tracing/events/sched/sched_blocked_reason/enable` | yes | yes |
| `/sys/kernel/tracing/per_cpu/cpu0/trace_pipe_raw` | yes | no |

This is **user-reported path-access preflight**, **not** successful
`open(2)`, tracing, record capture or KASLR. Read-only access to
`trace_pipe_raw` is the expected mode for BOPE's reader.
Other CPU reader paths remain unchecked. Shell tests may not
fully account for SELinux decisions at actual file-operation time.

**Important source-side hazard uncovered before runtime trials:** the
donor's `kaslr_locate_via_tracefs` (in `src/01_kernel_base_tracefs.c`)
writes `tracing_on=0`, truncates `trace`, enables the tracepoint,
writes `tracing_on=1`, and then ends by forcing `tracing_on=0`
and the event `enable=0` **without preserving/restoring original
values**. Thus `SLIDE_ONLY` is NOT a read-only or side-effect-free
on-device diagnostic; it can disrupt tracing state and destroy
existing trace data even without invoking the later futex kernel
mutation. Additionally, `PIPE_PREFLIGHT_ONLY` happens after
grooming and should not be treated as a harmless smoke test.

Before any controlled trace runtime experiment, use **read-only**
ADB to record `tracing_on` and `sched_blocked_reason/enable`
values, and establish a separate opt-in KASLR-only diagnostic with
an explicit snapshot/restore protocol, bounded runtime, and
safe-abort behavior. Do not run the WIP root payload, the
`SLIDE_ONLY` main orchestrator, or KernelSU on the phone yet.

### Read-only global tracing baseline before isolated test — 2026-10-15

The owner read the exact global TraceFS state via ordinary ADB shell:

```text
/sys/kernel/tracing/tracing_on: 0
/sys/kernel/tracing/events/sched/sched_blocked_reason/enable: 0
```

These are **user-reported read-only values**; they do not prove there
are no existing historical entries in the global tracing ring.

To avoid the donor resolver's destructive global `trace` truncation
and reset behavior, a narrow two-second **isolated trace instance**
smoke script was added at
`tools/android/gzif-isolated-trace-smoke.sh`.
It refuses a mismatched device identity; creates its own
`/sys/kernel/tracing/instances/rmg_gzif_<pid>` instance or aborts;
starts/stops only that instance's `sched_blocked_reason` event;
returns only an event **count**, plus an O_RDONLY no-consumption
open check for its CPU0 raw pipe. It never prints pointer values,
parses or infers the KASLR slide, or invokes BOPE/KernelSU. It uses
a shell EXIT trap to disable and remove its instance. If instance
creation is denied, **stop**; never fall back to the global
tracing controls.

Run manually on a connected owner device from Ubuntu WSL2
after `git pull --ff-only`:

```bash
ADB=/mnt/c/Android/platform-tools/adb.exe
SCRIPT=$HOME/Root-My-Galaxy-GZIF/tools/android/gzif-isolated-trace-smoke.sh
"$ADB" push "$(wslpath -w "$SCRIPT")" /data/local/tmp/gzif-isolated-trace-smoke.sh
"$ADB" shell sh /data/local/tmp/gzif-isolated-trace-smoke.sh
"$ADB" shell rm /data/local/tmp/gzif-isolated-trace-smoke.sh
```

**This diagnostic is not risk-free:** it briefly activates a kernel
tracepoint within an isolated instance, and cleanup is best-effort
(e.g., sudden process termination or kernel reboot can interrupt
it). It does not clear or write the global `trace` file, does not
test exploit behavior, and cannot establish root support. Do not
run it on a device performing critical work or when tracing is
being used for another diagnosis. Monitor `Instance cleanup: OK`;
if cleanup fails, preserve the error for inspection and do not
rerun automatically.

### Owner-reported isolated TraceFS refusal — 2026-10-15

The owner executed the opt-in native Android shell test
`tools/android/gzif-isolated-trace-smoke.sh` through an ordinary
non-root ADB shell after transferring the script to the phone.
The returned output was:

```text
GZIF_ISOLATED_TRACE_SMOKE_V1
Mode: separate tracefs instance; 2-second event count; no raw addresses
Result: INSTANCE_CREATION_DENIED — global tracing untouched
```

The `mkdir` for
`/sys/kernel/tracing/instances/rmg_gzif_<shell-pid>` was denied.
The test **stopped before any event enable or trace sampling**;
there is no `Instance cleanup` report because a private instance
was never created. It did not fall back to global TraceFS.
The precise cause of denial (mode bits, mount/kernel configuration,
SELinux or other policy) remains **unverified**, and this is **not**
a finding that KASLR, BOPE or root is impossible.

Earlier user-reported read-only global `tracing_on=0` and
`sched_blocked_reason/enable=0` values remain the last measured
baseline; the isolated script does not change those settings.
Do not call the legacy `SLIDE_ONLY` / resolver a benign fallback:
that code disables global tracing, truncates the global trace buffer,
and forces controls off rather than restoring prior values.
Further attempts to bypass instance permissions or alter system
trace policy are not authorized by this test outcome.

Next engineering gate: redesign/review BOPE's kernel-base resolver
**off-device** to make destructive global tracing changes impossible
by default and allow a safe, explicit abort when a non-disruptive
diagnostic cannot be run. No root payload, module or global-tracing
experiments should be performed solely on the strength of these
results.

## Controlled GZIF one-shot trial preparation — 2026-10-15

**Root was NOT attempted; the following is a source-only, off-device WIP
engineering step, not a validated flashing/rooting method.**

The generated GZIF candidate BOPE payload already compiled (owner reported
four ELF64/AArch64 outputs) and its separate Android native smoke passed on
the physical handset. An isolated tracefs instance experiment failed at
`mkdir`; the global trace controls were later observed at 0/0.
The original BOPE tracefs resolver still has destructive global trace
truncation, unguarded retries and donor-inherited unvalidated timings.

To prepare a *single-attempt source candidate* without modifying either
`targets/zzi8-WIP` or the owner's generated GZIF WIP tree, a
strict source overlay and opt-in build flag were added:

- `tools/linux/gzif_controlled_trial_overlay.py` operates only on the
  disposable staging copy in the existing isolated builder.
- It requires exact firmware identity as before and inserts an explicit
  runtime opt-in `GZIF_ONE_SHOT_ACK`; without it the payload
  **refuses before exploit preparation**.
- Forces `EXPLOIT_ATTEMPTS` to **one** regardless of environment.
- Refuses user-supplied cached/forced KASLR values.
- Removes the resolver's **global trace-file truncation**.
- Before touching TraceFS, requires both global `tracing_on` and
  `sched_blocked_reason/enable` to be exactly `0`. Any failure
  causes an abort.
- Tries to restore `0/0` and verify the result on normal completion.
  **This is best effort**, not an atomic tracing transaction:
  `trace_pipe_raw` can consume existing global ring records;
  concurrent trace users can interfere; `SIGKILL`, crashes or
  kernel reboot can prevent restoration. The 0/0 check does **not**
  prove that no historical trace data exist.
- Static source-drift and copy-isolation regressions are in
  `tools/bope/tests/test_gzif_controlled_trial_overlay.py`.

On **Ubuntu WSL2**, build a *host-side only* one-shot variant:

```bash
cd ~/Root-My-Galaxy-GZIF
git pull --ff-only origin port/s918n-gzif-android17
python3 -m unittest tools.bope.tests.test_gzif_controlled_trial_overlay -v
python3 tools/linux/build-gzif-android-wip.py --controlled-one-shot
```

A successful run places an overlay report and distinct
`HOST_BUILD_ONE_SHOT_EXPERIMENTAL_NOT_DEVICE_VALIDATED` build report in
a new directory under `~/rmg-firmware/gzif-android-builds/`.
It does not transfer, execute, or install anything on Android. **Do not
deploy the one-shot candidate just because it compiled**.

**Pending before owner-authorized device exploit trial:** review
the resulting build and exact runtime environment; evaluate the trace
record encoding and recoverability if globals cannot be restored;
confirm no new unresolved boot or kernel-version assumptions; verify
the prepared Odin/official-firmware recovery path; and separately
resolve KernelSU module admission policy. Root helper success and
KernelSU persistent root must not be conflated.

### Owner-confirmed controlled one-shot host build — 2026-10-15

The owner executed `python3 tools/linux/build-gzif-android-wip.py
--controlled-one-shot` after obtaining the source overlay. The local
**isolated host-side NDK build** succeeded:

```text
[ONE-SHOT] Prepared GZIF-only guarded source copy
[BUILT] payload_so: ELF64/AArch64 (165864 bytes)
[BUILT] mm_exec_factory: ELF64/AArch64 (1816 bytes)
[BUILT] stability_launcher: ELF64/AArch64 (18736 bytes)
[BUILT] root_helper: ELF64/AArch64 (28240 bytes)
Status: HOST_BUILD_ONE_SHOT_EXPERIMENTAL_NOT_DEVICE_VALIDATED
DO NOT DEPLOY these WIP binaries to Android.
One-shot overlay is NOT a safety certification.
```

Local report, **not uploaded**:
`~/rmg-firmware/gzif-android-builds/s918ngzif-dbc32o5g/build-report.json`.
Source owner output shows compiler and three existing host regressions
succeeded under the build script. Results of the **six distinct
`test_gzif_controlled_trial_overlay` cases have not yet been
provided**; do not infer they passed.

**No root attempt or KernelSU module load occurred**. The new
`payload.so` is not safe to deploy merely because it compiled.
Source-review blockers include read/consumption of global
`trace_pipe_raw` rings, non-atomic TraceFS state changes,
absence of robust signal/crash restoration, donor-inherited
kernel allocator/timing calibration and an unverified unsigned
KernelSU module admission path. Do not copy or run the payload
until the actual on-device trial has an independently reviewed
recovery and rollback plan.

### Owner-reported recovery resources before root trial — 2026-10-15

The owner answered that **all recovery resources are ready** after being
asked specifically about a full matching SM-S918N firmware package,
Windows Odin and backups. This is an **operator statement only**; no
contents, firmware hashes, partition compatibility, working Download Mode
entry, or actual data-restore test have been independently verified.
Having recovery files is not proof that user data are recoverable
after a kernel panic or partition damage.

The isolated GZIF one-shot WIP NDK build has completed and remains
off-device. **The six dedicated one-shot source-overlay regressions
have not been provided in the conversation**, and the build alone
does not prove the patched tracing error paths. The donor engine's
launcher provides `--check-only`, which checks runtime stability,
mm geometry and pipe capacity without loading BOPE; that is a
preflight, not the root trial. A true root attempt would run the
unvalidated futex/allocator sequence and could immediately
crash/reboot the kernel. It must not be conflated with the
previous harmless GZIF identity smoke.

No payload deployment or rooting attempted at this checkpoint.
A root-trial release gate requires review of the exact artifact,
positive overlay regressions, isolated device preflight, checked
rollback plan and explicit notice that temporary root is not
the same as KernelSU persistence.

### Owner-confirmed six one-shot overlay regressions — 2026-10-15

The owner executed
`python3 -m unittest tools.bope.tests.test_gzif_controlled_trial_overlay -v`
on the WSL checkout and reported:

```text
----------------------------------------------------------------------
Ran 6 tests in 0.013s

OK
```

This clears the **source-overlay regression gate** in the owner's
environment; the exact console output provided did not include
the names of the six cases. It does not validate tracefs interaction,
kernel memory manipulation or root on the physical device.

The **next diagnostic gate**, not an exploit invocation, is the existing
GZIF-built stability launcher in `--check-only` mode. Source review
confirmed `--check-only` does not load `payload.so` or call `execve`,
but does check the expected `mm_struct` layout, sample CPU/memory/
thermal metrics for up to 300 seconds, and transiently create 480
pipes, resizing each to 32 x 4-KiB capacity as a resource-capability
probe (without writing the pipe buffers). It may fail by design
under ordinary Samsung SELinux/capability/rlimit policy and must not
be bypassed. This test is **not** risk-free and not proof of exploit
readiness. Do not transfer or run the root helper or payload in this
diagnostic stage.

### On-device launcher check-only PASS — 2026-10-15

The owner executed the *actual GZIF-built* stability launcher on the
physical SM-S918N with `--check-only` using ADB shell. Console report:

```text
[launcher] mm-geometry=pass size=1024 per=32 pages=8 active=592 total=704
[launcher] gate s918ngzif-fresh: 3 amostras/2s (fast 2/1s) temp<=48C mem>=1GB tarefas<=8 PSI<=25/3/5 uptime>=60s mm-delta<=64 pipe=480x32 timeout=300s
[launcher] pipe-gate=pass pipes=480 target_pages=32
[launcher] gate=1/3 phase=fast temp=38.0C mem=3264MB runnable=1 load=0.77 psi=3.25/0.02/0.04 mm=592/704 slabs=22 dmm=0 uptime=55375s boot=1 se=1
[launcher] gate=2/3 phase=fast temp=38.0C mem=3264MB runnable=1 load=0.77 psi=3.20/0.01/0.03 mm=592/704 slabs=22 dmm=0 uptime=55376s boot=1 se=1
[launcher] mm-geometry=pass size=1024 per=32 pages=8 active=592 total=704
[launcher] estabilidade confirmada: métricas+slab+pipe
```

**Result: runtime stability gate passed.** The 480-pipe resizing
probe completed, the live mm_struct geometry matched the header,
the device remained enforcing and the short fast profile met thresholds.
`--check-only` returned before setting `LD_PRELOAD`: no BOPE exploit
or root helper was executed. The console excerpt does not include
the actual process exit code; success is inferred from the successful
final launcher line. Kernel heap reclaim and futex timing remain
unverified. A pass here is **not root readiness**.

Post-review the source overlay gained a **separate** pre-root
`GZIF_KASLR_ONLY` mode (commit `b8eb590`) that calls the KASLR
resolver before any `root_umh_preflight` file writes/trigger exec,
without touching kernel heap/futex. The ordinary donor
`SLIDE_ONLY`, `P0_ONLY` and `PIPE_PREFLIGHT_ONLY` are refused
in this overlay because they may run root preparation first.
The root-mutation path also requires a distinct acknowledgement
`GZIF_KERNEL_MUTATION_ACK`; merely permitting KASLR must
not accidentally authorize root payload execution.

KASLR-only **is still a live tracing experiment**: the resolver
enables global TraceFS temporarily and reads consumptive
`trace_pipe_raw` records. The cleanup is best effort on normal
completion, and SIGKILL/abrupt reboot may leave tracing enabled.
No KASLR diagnostic or kernel mutation has yet been executed.

After this source modification the previous four-artifact build is
**stale** and must not be used for new diagnostic mode; host overlay
regressions and NDK rebuild must be repeated.

### Owner-reported latest GZIF one-shot build and root go/no-go — 2026-10-15

After the explicit pre-root KASLR-only branch and separate
kernel-mutation acknowledgement were added, the owner reported:

```text
Ran 8 tests in 0.004s
OK
[ONE-SHOT] Prepared GZIF-only guarded source copy
[BUILT] payload_so: ELF64/AArch64 (166560 bytes)
[BUILT] mm_exec_factory: ELF64/AArch64 (1816 bytes)
[BUILT] stability_launcher: ELF64/AArch64 (18736 bytes)
[BUILT] root_helper: ELF64/AArch64 (28240 bytes)
Status: HOST_BUILD_ONE_SHOT_EXPERIMENTAL_NOT_DEVICE_VALIDATED
```

The new disposable host build was located at
`~/rmg-firmware/gzif-android-builds/s918ngzif-abe9924m/`.
This supersedes the older `s918ngzif-dbc32o5g` outputs.
The user also previously reported the actual on-device
`stability-launcher --check-only` PASS (mm geometry,
480-pipe resource gate and environment measurements).

**GO**: source tests passed; latest host build completed;
the launcher preflight ran on-device successfully.

**NO-GO for running the BOPE kernel-mutation/root stage:** there
has been *no* GZIF on-device BOPE KASLR slide resolution or
validation of the trace ring encoding, no device-validated
allocator/reclaim/futex window, and no proven GZIF KernelSU module
load admission under the Samsung GKI protected-symbol policy.
The WIP source overlay still toggles **global** tracing and reads
consumptive raw trace ring data; restoring global state after
kernel crash/SIGKILL is not guaranteed. One-shot limits
repetition, but cannot prevent a first-attempt kernel panic,
stale pointer dereference, data loss or bootloop.

The owner has stated backup, official firmware and Windows Odin
are ready, but no full restore was demonstrated. Running the
latest staged payload or treating temporary UMH access as a
working KernelSU root install is not justified by the observed
results. **No exploit was triggered, and root remains unverified.**

## BOPE + KernelSU Next full-root integration (not Magisk)

The exact source-level root chain, late-load state transitions,
kernel module provenance gap, SELinux/UMH restoration requirements and
next kernel-engineering milestones are documented in
[ROOT_CHAIN.md](ROOT_CHAIN.md).

The owner's reported state remains: **8/8 overlay tests PASS, four
Android NDK outputs built, on-device `stability-launcher --check-only`
PASS; no live BOPE kernel mutation, temporary-root result or KernelSU
module admission has been observed.** A future temporary root socket
must not be reported as a completed KernelSU root installation.

### Owner-confirmed first live BOPE KASLR-only resolution — 2026-10-15

The owner ran **the guarded BOPE `GZIF_KASLR_ONLY` payload** on
the actual SM-S918N/GZIF device and reported:

```text
TraceFS before: 0/0
[BOPE] Brazilian Open Payload Engine initialized
[BOPE] [*] starting exploit attempts=1
[BOPE] [*] exploit attempt=1/1
[kaslr] source=tracefs base=(redacted) slide=(redacted) p0_offset=(redacted) votes=2 sample_ms=0
[BOPE] [+] exploit completed attempt=1/1
TraceFS after: 0/0
KASLR exit code: 0
```

**Outcome:** the actual KASLR resolver ran and returned a candidate
kernel base meeting its configured two-vote quorum. Global TraceFS
controls were observed as `0/0` before and after the process.
No root stage, futex kernel mutation, arbitrary kernel R/W, KernelSU
module load or SELinux transition has been demonstrated.

**Qualification:** `sample_ms=0` indicates that the reported success
was immediate or elapsed-time rounded to zero. Because global
`trace_pipe_raw` rings were **not cleared** (to preserve existing
tracing data), the source records could have been buffered earlier.
Also, the resolver's loose record scan does not provide an
independent, fresh kernel-base confirmation. Its candidate is
**not yet proven correct for memory mutation**. No absolute kernel
addresses are recorded in this public report.

**Observed logging mismatch:** BOPE's default compact logger passes
`[kaslr] source=` and generic `exploit completed` but silently
filters `[gzif-diagnostic]` because it is not on the allowlist.
This made the *KASLR-only* success appear as an actual exploit success
even though the dedicated mode returns before kernel mutation.

**Fix:** the one-shot GZIF-only source overlay now emits
`stage=gzif-kaslr-...` so compact logging will show the
`root-not-attempted` qualifier, and changes the parent supervisor
log label for this mode from `exploit completed` to
`stage=gzif-kaslr-child-completed root-not-attempted`.
A ninth host regression test covers these statements. The original
ZZI8 donor source is unchanged. This is a **new host source revision**;
the previously run `s918ngzif-abe9924m` artifact is
not patched retroactively.

**No-GO for BOPE kernel memory mutation/root:** validating that an
algorithm produced a two-vote candidate does not independently prove
the candidate was derived from fresh current-boot trace records.
GZIF allocator/reclaim timing and unsigned KernelSU Next module
admission still lack live validation. Odin/backup readiness cannot
make those kernel writes reliable.

### GZIF KASLR page-deduplication source hardening — 2026-10-15

Reviewing the actual `01_kernel_base_tracefs.c` established the
meaning of the owner-observed `sample_ms=0`: the monotonic timer
starts **after** the two `prime_block_io()` passes (each pass writes
a multi-megabyte temporary I/O stimulus and fsyncs it). Therefore
`sample_ms=0` is compatible with trace records generated during
those passes, and is **not itself evidence of stale ring data**.
The initial KASLR candidate was produced by a two-vote quorum;
this remains real execution evidence, not proof of a correct slide.

Further inspection found that the donor's loose scan
(`parse_trace_page`) can count two matching records **on the same
raw trace page** as a complete two-vote quorum, even if the records
are duplicates. This source assumption was not covered by the
previous one-shot regression tests.

A new **GZIF-only disposable-copy overlay** now runs the
existing parser against a *per-page temporary vote table* and
merges at most one vote per candidate from each separately
read TraceFS page. A successful quorum requires records from
at least `TARGET_KASLR_QUORUM` separate page reads (two for
the donor contract). The patch also records
`stage=gzif-tracefs-live-capture-ms=` beginning **before** the two
I/O priming passes, while preserving the original `sample_ms`
field for comparison.

A new compiled host fixture creates synthetic trace data with
two matching loose-format records **in one page**, confirms
this cannot satisfy a two-vote quorum, then feeds two pages
and confirms the exact candidate resolves. The host regression
suite now has **12 cases** (including this compiled C case),
but **these 12 updated tests have not yet been executed by the
owner**. Successful test/build output is required before using
this revised binary; the previously tested `abe9924m`
payload is unchanged and uses the old quorum logic.

**Remaining limitations:** two different pages may still contain
stale records from a prior global tracing session, and the
loose scanner accepts candidates based on event ID and caller
range without fully validated structured event metadata. Two
independent page reads reduce duplicate-vote risk but
do not cryptographically establish source freshness or
guarantee correctness of kernel memory addresses. No root
experiment has been authorized by these changes.

### Owner-confirmed revised GZIF overlay regressions — 2026-10-15

The owner first reported **11 PASS / 1 FAIL** in 12
`test_gzif_controlled_trial_overlay` cases, while the latest
four-artifact Android NDK build **succeeded** at:

`~/rmg-firmware/gzif-android-builds/s918ngzif-7cjfl28m/`

The single failure was a stale test assertion checking for
`root not attempted` after the guarded KASLR-only diagnostic
was changed to `root-not-attempted`. The runtime source itself
built without an error. Commit `b9b8b94` corrected the
assertion without changing BOPE or the NDK build artifacts.

The owner has now explicitly confirmed **12/12 OK** after the
assertion fix. This is a successful **host regression run**
(including synthetic-page compiled C test), not evidence
that the revised two-distinct-page KASLR quorum has executed
on the physical SM-S918N.

**Next owner trial, not yet observed:** guarded
`GZIF_KASLR_ONLY` mode using the above rebuilt
`s918ngzif-7cjfl28m` payload; look for
`stage=gzif-kaslr-distinct-pages-quorum=2`,
`stage=gzif-tracefs-live-capture-ms=`,
and TraceFS `0/0` restoration. This is not
kernel mutation, temporary root, or KernelSU load.

### Owner-confirmed live GZIF two-page KASLR success — 2026-10-15

The owner ran the updated `s918ngzif-7cjfl28m` guarded
`GZIF_KASLR_ONLY` payload on the physical SM-S918N
and confirmed:

```text
TraceFS before: 0/0
[BOPE] stage=gzif-kaslr-only no-root-preflight no-kernel-mutation
[BOPE] stage=gzif-kaslr-distinct-pages-quorum=2
[BOPE] stage=gzif-tracefs-live-capture-ms=67
[kaslr] source=tracefs base=(redacted) slide=(redacted) p0_offset=(redacted) votes=2 sample_ms=2
[BOPE] stage=gzif-kaslr-resolved root-not-attempted
[BOPE] stage=gzif-kaslr-child-completed root-not-attempted
[BOPE] stage=gzif-kaslr-only-success root-not-attempted
TraceFS after: 0/0
KASLR exit code: 0
```

**Observed success:** updated BOPE loaded and ran on GZIF;
it found a candidate passing two votes drawn from **two separately
read raw TraceFS pages**. The capture-inclusive window was
67 ms; the old post-prime read window was 2 ms. The reported
candidate was consistent with the previous test on this boot.
Global tracing controls were `0/0` before and after.
The initial 12 host tests have been confirmed PASS,
and the four NDK binaries built successfully.

**Explicitly not proven:** no direct independent validation
of the candidate kernel address; TraceFS rings may retain
older records, even though the separate-page quorum now
reduces duplicated-record failure modes. **No futex/slab
kernel mutation, kernel R/W, temporary root helper, SELinux
change, KernelSU module load or persistent root occurred.**

**Next engineering gate:** validate the *actual* root helper
and binfmt/UMH path against the target userland and protected
kernel policy, and review the donor-inherited futex allocator
and recovery assumptions before any device kernel-mutation
attempt. This completed KASLR-only experiment need not be
repeated without new diagnostic need. The analysis-only
vermagic-patched donor KSU module remains off-device.

### Pinned KernelSU Next ksud integration builder — 2026-10-15

The actual BOPE root helper's late-load route expects
`/data/local/tmp/ksud-selected`, a separate userspace executable
that the existing four-artifact GZIF BOPE NDK builder never produces.

The upstream **KernelSU Next v3.4.0** implementation of `ksud
late-load` selects the embedded `android13-5.15_kernelsu.ko`
module, calls the `ksuinit` `init_module` loader (with
symbol relocation support and a conditional vermagic fallback),
then checks its control channel. The original ZZI8 prebuilt
module still has unproven Samsung/GZIF load admission.

Added host-only `tools/linux/build-gzif-ksud-loader-wip.py`,
which makes an isolated copy of the previously pinned
`1a879d6` upstream source, checks the unchanged developer
module against its known SHA-256, confirms the local GZIF
metadata-only candidate differs **only** in the vermagic
field and has the previously generated successful static audit,
embeds that module into the exact RustEmbed KMI asset path,
and builds the actual AArch64 Android `ksud` via Cargo/NDK.
The output is named `ksud-selected.WIP` and its provenance
is saved in a local JSON report.

**This is a new integration builder, not a confirmed owner build**:
the owner has not yet reported its Cargo result. It is
explicitly off-device, unsigned and not a supported root install.
No Samsung kernel module admission or BOPE kernel mutation
has been validated by constructing this userspace loader.
See [ROOT_CHAIN.md](ROOT_CHAIN.md) for the build command and
remaining separate root gates.

### Owner-confirmed real KernelSU Next Android `ksud` host build — 2026-10-15

The host-only `build-gzif-ksud-loader-wip.py` completed successfully
on the owner's Ubuntu WSL after installing Rust and correcting the
audit report schema contract:

- Upstream KernelSU Next v3.4.0 source commit: pinned `1a879d6`.
- Embedded KMI module: `android13-5.15_kernelsu.ko`, using the
  **static-audited ZZI8 donor-derived candidate with GZIF
  vermagic**, not an exact-source rebuild.
- Output: `ksud-selected.WIP`, **ELF64/AArch64, 4,246,104 bytes**.
- Build directory:
  `~/rmg-firmware/gzif-kernelsu-loader-builds/s918ngzif-ksud-ohhjnre7/`
- Cargo build report: `build-report.json` in that directory.
- Owner output: `Status: HOST BUILT; device module admission NOT validated`.

**Milestone:** the BOPE temporary-root helper's intended
`ksud-selected` loader now has an actual matching-command-line
Android binary *on the host*. This does **not** constitute a
GZIF-native `kernelsu.ko` nor establish kernel module load
admission, KernelSU control, or SELinux recovery. No device
deployment or root run has been performed with these files.

See [ROOT_CHAIN.md](ROOT_CHAIN.md) for the next distinct
kernel-execution, temporary-root and KernelSU loading gates.
No repeat of already-passed BOPE KASLR or host regressions
is called for.

### GZIF SELinux fallback fuse in controlled root helper — 2026-10-15

Follow-up code review of the original BOPE temporary-root
bootstrap found that a successful UMH result leaves SELinux
permissive until a **later, separate** KernelSU `late-load`
request restores enforcing. A socket that receives no
late-load request may otherwise remain open indefinitely.

Added `tools/linux/gzif_root_helper_guard.py` and
`tools/linux/build-gzif-fused-helper-only.py` as
**GZIF-specific, isolated-source host tools**. They overlay
the generated root helper (not the shared donor), add
a separate best-effort **180-second watchdog** that
attempts SELinux enforcing restoration, and limit new
temporary-root socket accepts to the same deadline.
Socket setup errors attempt immediate recovery.

The new builder compiles **only** the modified helper,
reusing the existing successful native build report and
source; it does not rebuild BOPE/ksud or repeat their
already-passed regressions. `assemble-gzif-rootchain-host-only.py`
now accepts `--fused-helper-report` to create a separately
named, hash-checked **host-only** snapshot with the new helper.

**Owner-confirmed host compilation (2026-10-15):**
the GZIF-only SELinux-fused root helper built successfully as
a **29,528-byte ELF64/AArch64 binary** with a separate
report at
`~/rmg-firmware/gzif-helper-fuse-builds/s918ngzif-helper-fuse-njug65hu/build-report.json`.
The host-only report says `HOST_BUILT_FUSE_ONLY`.
Only the changed root helper was recompiled; existing
BOPE and `ksud` binaries were not rebuilt.

**Not verified on device:** watchdog execution, temporary
root, Samsung module admission or SELinux restoration.
The watchdog cannot recover from kernel panic, power loss,
simultaneous process deaths or UMH failure before it
is spawned, and existing sessions may outlive the
socket accept deadline. These controls do **not** make
the kernel-mutation exploit safe or authorize deployment.
See [ROOT_CHAIN.md](ROOT_CHAIN.md) for the optional
new host-only five-file assembly with the guarded helper.

## Remaining validation gates

1. Recover GZIF-specific kernel symbols from the provided boot and generate a
   symbolized `vmlinux.elf` using the upstream porting pipeline.
2. Regenerate and verify every BOPE firmware-specific static offset and
   maintain an explicit list of donor-inherited timing/calibration values.
3. Rebuild and audit KernelSU Next against GZIF's actual kernel ABI and module
   versioning, then compile the payload and its helpers with the matching NDK.
4. Confirm exact runtime identity, safe failure and reproducibility across
   multiple clean boots on the owner's **SM-S918N** device. Keep SELinux and
   protected partitions intact.
5. Only then bundle the resulting verified artifacts into the app and publish
   a supported target/release.

## Generate a WIP target from the supplied standalone LZ4

Use the full upstream source checkout and prerequisite tools described in
[the upstream porting guide](https://github.com/soumarcelino/Root-My-Galaxy-SM-S918B/blob/main/tools/bope/README.md).

```sh
./tools/bope-from-factory "/path/to/boot.img.lz4" \
  --fingerprint 'samsung/dm3qksx/dm3q:17/CP2A.260605.016/S918NKSU8GZIF:user/release-keys' \
  --donor targets/zzi8-WIP \
  --engine-donor targets/zzi8-WIP \
  --target-slug s918ngzif \
  --expected-kernel-release 5.15.197-android13-8-34343818-abS918NKSU8GZIF \
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
