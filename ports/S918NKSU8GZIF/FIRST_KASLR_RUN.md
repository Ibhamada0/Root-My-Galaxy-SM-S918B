# GZIF live BOPE kernel-base stage — owner opt-in protocol

Target: **Samsung SM-S918N, S918NKSU8GZIF only**.

**Not a full root run.** This executes the **actual BOPE KASLR
resolver** on the owner handset, but uses the guarded
`GZIF_KASLR_ONLY` mode that returns *before* root helper preparation,
slab reclaim, futex memory corruption, arbitrary kernel R/W and KernelSU
load. A successful output is **KASLR resolved**, *not root*.

This stage is not read-only: BOPE uses the global tracefs
`tracing_on` and event `enable` controls for a bounded period and
reads/consumes `trace_pipe_raw` ring records. Its `prime_block_io`
also writes temporary I/O stimulus data under
`/data/local/tmp`. The stage will refuse a non-idle global
trace baseline but cannot prevent other trace users racing or
guarantee state restoration after a crash or SIGKILL.
The earlier isolated-instance experiment was denied.

## Owner-accepted on-device KASLR-only run

Use the **owner-reported 8/8 tested** one-shot build, not the older
payloads. From Ubuntu WSL2 with an already authorized phone:

```bash
ADB=/mnt/c/Android/platform-tools/adb.exe
OUT="$HOME/rmg-firmware/gzif-android-builds/s918ngzif-abe9924m"
PAYLOAD="$OUT/targets/s918ngzif-WIP/brazilian-open-payload-engine/build/payload.so"
test -f "$PAYLOAD" || { echo "Missing expected guarded GZIF payload"; exit 2; }

"$ADB" push "$(wslpath -w "$PAYLOAD")" /data/local/tmp/gzif-kaslr-only.so
"$ADB" shell chmod 700 /data/local/tmp/gzif-kaslr-only.so
```

Opt in **only when idle** and when no other tracing/debugger is
using global TraceFS. No helper, KernelSU `.ko`, or ksud binary
should be pushed.

```bash
"$ADB" shell '
  R=/sys/kernel/tracing
  T="$R/tracing_on"
  E="$R/events/sched/sched_blocked_reason/enable"
  t=$(cat "$T") || exit 2
  e=$(cat "$E") || exit 2
  echo "TraceFS before: tracing_on=$t event_enable=$e"
  if [ "$t" != "0" ] || [ "$e" != "0" ]; then
    echo "ABORT: global tracing not idle; not attempting BOPE"
    exit 2
  fi

  GZIF_ONE_SHOT_ACK=I_ACCEPT_GZIF_ONE_SHOT_RISK_S918NKSU8GZIF \
  GZIF_KASLR_ONLY=1 \
  BOOT_QUIET_SEC=0 \
  TRACEFS_SAMPLE_SECONDS=2 \
  LD_PRELOAD=/data/local/tmp/gzif-kaslr-only.so \
  /system/bin/true

  result=$?
  t=$(cat "$T")
  e=$(cat "$E")
  echo "TraceFS after: tracing_on=$t event_enable=$e"
  echo "KASLR-only process exit code: $result"
  if [ "$t" != "0" ] || [ "$e" != "0" ]; then
    echo "WARNING: unexpected TraceFS state. Do not retry; inspect."
  fi
  exit "$result"
'
```

If `LD_PRELOAD` is denied by the linker or SELinux, report the
error; do not bypass Android policy. If the run hangs, the BOPE
supervisor has a pre-mutation timeout, **but SIGKILL may prevent
TraceFS cleanup**. Do not repeatedly attempt this experiment.

After noting the result, remove the test library:

```bash
"$ADB" shell rm /data/local/tmp/gzif-kaslr-only.so
```

When sharing the console output, **redact any printed kernel
`base=` or `slide=` hexadecimal address**, but preserve the
`source=`, `votes=`, `sample_ms=`, `KASLR ...`,
`TraceFS before/after` and exit status lines so we can
distinguish no records, parser mismatch, access denial and
successful location.

## Result interpretation

- `[gzif-diagnostic] KASLR resolved; root not attempted`: the
  BOPE slide resolver achieved its vote quorum, **no root**.
- `worker_thread quorum not reached`: no slide proven; an
  inherited record format or caller offset may be wrong.
- Any nonzero TraceFS after-state, kernel crash/reboot, or
  unexpected permissions: **STOP**, do not try the full root
  payload or rerun automatically.
- A generic parent log reading `exploit completed` refers
  only to the child status and is **not** kernel exploit success
  in `GZIF_KASLR_ONLY` mode.

A later BOPE kernel-mutation and KernelSU trial requires
separate firmware-specific evidence. The unsigned
vermagic-retargeted donor `.ko` remains unvalidated;
do not load or flash it from this protocol.
