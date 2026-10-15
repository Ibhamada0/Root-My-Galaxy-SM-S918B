#!/system/bin/sh
# SM-S918N GZIF: bounded, isolated tracefs event smoke test.
# No BOPE, KernelSU, trace buffer clearing, kernel memory access or root.
# Only manipulates a NEW private tracefs instance; never falls back to global.
set -eu

root=/sys/kernel/tracing
expected_build=S918NKSU8GZIF
expected_release=5.15.197-android13-8-34343818-abS918NKSU8GZIF
expected_model=SM-S918N
expected_device=dm3q
expected_fp=samsung/dm3qksx/dm3q:17/CP2A.260605.016/S918NKSU8GZIF:user/release-keys

echo "GZIF_ISOLATED_TRACE_SMOKE_V1"
echo "Mode: separate tracefs instance; 2-second event count; no raw addresses"
if [ "$(getprop ro.build.version.incremental)" != "$expected_build" ] ||
   [ "$(getprop ro.product.model)" != "$expected_model" ] ||
   [ "$(getprop ro.product.device)" != "$expected_device" ] ||
   [ "$(getprop ro.build.fingerprint)" != "$expected_fp" ] ||
   [ "$(uname -r)" != "$expected_release" ]; then
    echo "Result: IDENTITY_MISMATCH — no tracing changed"
    exit 2
fi

# Prior owner checks showed global tracing_on=0, event enable=0; this
# program DOES NOT modify or read/clear the global trace buffer.
instance="$root/instances/rmg_gzif_$$"
if [ ! -d "$root/instances" ]; then
    echo "Result: INSTANCES_UNAVAILABLE — global tracing untouched"
    exit 3
fi
if ! mkdir "$instance" 2>/dev/null; then
    echo "Result: INSTANCE_CREATION_DENIED — global tracing untouched"
    exit 3
fi

event="$instance/events/sched/sched_blocked_reason/enable"
active="$instance/tracing_on"
trace="$instance/trace"
raw="$instance/per_cpu/cpu0/trace_pipe_raw"

cleanup() {
    rc=$?
    trap - 0 1 2 3 15
    set +e
    (printf '0\n' > "$active") >/dev/null 2>&1
    (printf '0\n' > "$event") >/dev/null 2>&1
    if rmdir "$instance" >/dev/null 2>&1; then
        echo "Instance cleanup: OK"
    else
        echo "Instance cleanup: FAILED — check $instance, do not retry automatically"
        rc=5
    fi
    exit "$rc"
}
trap cleanup 0
trap 'exit 129' 1
trap 'exit 130' 2
trap 'exit 131' 3
trap 'exit 143' 15

if [ ! -f "$event" ] || [ ! -f "$active" ] || [ ! -r "$trace" ]; then
    echo "Result: INSTANCE_EVENT_FILES_UNAVAILABLE"
    exit 3
fi

# Configure only the just-created instance. Never use global 'trace' or
# 'tracing_on', and never truncate any trace buffer.
if ! printf '0\n' > "$active"; then
    echo "Result: CANNOT_PAUSE_PRIVATE_INSTANCE"
    exit 3
fi
if ! printf '0\n' > "$event"; then
    echo "Result: CANNOT_DISABLE_PRIVATE_EVENT"
    exit 3
fi
if ! printf '1\n' > "$event"; then
    echo "Result: CANNOT_ENABLE_PRIVATE_EVENT"
    exit 3
fi
if ! printf '1\n' > "$active"; then
    echo "Result: CANNOT_START_PRIVATE_TRACING"
    exit 3
fi

sleep 2

if ! printf '0\n' > "$active"; then
    echo "Result: CANNOT_STOP_PRIVATE_TRACING"
    exit 3
fi
if ! printf '0\n' > "$event"; then
    echo "Result: CANNOT_DISABLE_PRIVATE_EVENT_AFTER_SAMPLE"
    exit 3
fi

# Only report a count; do not output trace records with kernel pointers.
if count=$(grep -c 'sched_blocked_reason:' "$trace" 2>/dev/null); then
    :
else
    rc=$?
    if [ "$rc" -ne 1 ]; then
        echo "Result: PRIVATE_TRACE_READ_FAILED"
        exit 3
    fi
fi
echo "sched_blocked_reason event lines: $count"
if [ -e "$raw" ]; then
    # Actual open(2) test without reading/consuming raw trace data.
    if dd if="$raw" of=/dev/null bs=4096 count=0 2>/dev/null; then
        echo "cpu0 trace_pipe_raw open: OK"
    else
        echo "cpu0 trace_pipe_raw open: DENIED"
    fi
else
    echo "cpu0 trace_pipe_raw: UNAVAILABLE"
fi
echo "Result: PRIVATE_INSTANCE_RUN_COMPLETED (not a KASLR/root test)"
