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
