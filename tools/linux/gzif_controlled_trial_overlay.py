"""Source-only GZIF one-shot trial overlay, applied to a COPIED WIP engine.

Never patches the ZZI8 donor or the owner's generated GZIF source.
No Android/device I/O. Changes are fail-closed if upstream code drifts.
This does not establish safe kernel exploitation.
"""
from __future__ import annotations

from pathlib import Path

ACK = "I_ACCEPT_GZIF_ONE_SHOT_RISK_S918NKSU8GZIF"


def once(text: str, old: str, new: str, label: str) -> str:
    matches = text.count(old)
    if matches != 1:
        raise ValueError(f"{label}: expected one exact source anchor, found {matches}")
    return text.replace(old, new, 1)


def patch_orchestrator(text: str) -> str:
    guard_at = '  int boot_quiet_sec = env_int_clamped("BOOT_QUIET_SEC", 120, 0, 300);'
    guard = (
        '  /* GZIF controlled trial: never run automatically or on donor builds. */\n'
        '  const char *gzif_ack = getenv("GZIF_ONE_SHOT_ACK");\n'
        f'  if (!gzif_ack || strcmp(gzif_ack, "{ACK}") != 0) {{\n'
        '    fprintf(stderr, "[gzif-trial] refusing without explicit opt-in\\n");\n'
        '    return 1;\n'
        '  }\n'
        '  if (getenv("SLIDE_P0_OFFSET") || getenv("P0_GATE_PAGE_STRUCT") ||\n'
        '      getenv("P0_PROBE_PAGE_STRUCT")) {\n'
        '    fprintf(stderr, "[gzif-trial] refusing forced/cached KASLR inputs\\n");\n'
        '    return 1;\n'
        '  }\n\n'
    )
    text = once(text, guard_at, guard + guard_at, "explicit trial opt-in")
    text = once(
        text,
        'int attempts = env_int_clamped("EXPLOIT_ATTEMPTS", 8, 1, 0x40);',
        'int attempts = 1; /* GZIF: one attempt only, irrespective of environment */',
        "single attempt limit",
    )
    return text


def patch_tracefs(text: str) -> str:
    header_at = "int kaslr_locate_via_tracefs(uint64_t *kernel_base_out) {"
    helpers = r"""/* GZIF trial: preserve a quiescent global TraceFS control baseline.
 * Deny if another tracing user has active controls. No trace truncation.
 * On SIGKILL/reboot, cleanup cannot be guaranteed; see the trial README.
 */
static int gzif_tracefs_is_zero(const char *path) {
  int fd = open(path, O_RDONLY | O_CLOEXEC);
  if (fd < 0) return 0;
  char c = '\0';
  ssize_t got = read(fd, &c, 1);
  close(fd);
  return got == 1 && c == '0';
}

static int gzif_tracefs_reset(const char *tracing_on,
                              const char *event_enable) {
  int stop = tracefs_write(tracing_on, "0");
  int disable = tracefs_write(event_enable, "0");
  return stop && disable && gzif_tracefs_is_zero(tracing_on) &&
         gzif_tracefs_is_zero(event_enable);
}

"""
    text = once(text, header_at, helpers + header_at, "trace safety helpers")
    begin = '  static const char trace[] = TRACEFS_ROOT "/trace";'
    end = "  prime_block_io();"
    if text.count(begin) != 1 or text.count(end) != 2:
        # The donor has two consecutive prime_block_io() calls.
        raise ValueError("Unexpected tracefs resolver layout")
    start = text.index(begin)
    finish = text.index(end, start)
    if finish <= start or finish - start > 2000:
        raise ValueError("Unexpected tracefs control block extent")
    original = text[start:finish]
    required = [
        'static const char event_enable[]',
        'tracefs_write(tracing_on, "0")',
        'O_TRUNC',
        'tracefs_write(event_enable, "1")',
        'tracefs_write(tracing_on, "1")',
    ]
    if any(piece not in original for piece in required):
        raise ValueError("Unexpected destructive tracefs block; refusing patch")
    replacement = r"""  static const char event_enable[] =
      TRACEFS_ROOT "/events/sched/sched_blocked_reason/enable";

  if (!gzif_tracefs_is_zero(tracing_on) ||
      !gzif_tracefs_is_zero(event_enable)) {
    fprintf(stderr, "[gzif-kaslr] global tracing is not idle; refusing\n");
    return 0;
  }

  /* The owner observed 0/0 in the read-only baseline. This trial
   * changes ONLY these two controls temporarily, never truncates /trace.
   * trace_pipe_raw consumption and concurrent tracers remain risks.
   */
  if (!tracefs_write(event_enable, "1")) {
    fprintf(stderr, "[gzif-kaslr] event enable rejected\n");
    return 0;
  }
  if (!tracefs_write(tracing_on, "1")) {
    fprintf(stderr, "[gzif-kaslr] tracing enable rejected\n");
    if (!gzif_tracefs_reset(tracing_on, event_enable))
      fprintf(stderr, "[gzif-kaslr] WARNING: cleanup failed\n");
    return 0;
  }

"""
    text = text[:start] + replacement + text[finish:]
    # The original function has two early exits after controls were enabled:
    # no CPUs and failed allocations. Do not leave tracing active.
    early = (
        '    tracefs_write(tracing_on, "0");\n'
        '    tracefs_write(event_enable, "0");\n'
        '    return 0;'
    )
    if text.count(early) != 2:
        raise ValueError("Unexpected number of tracefs early exits")
    text = text.replace(
        early,
        '    if (!gzif_tracefs_reset(tracing_on, event_enable))\n'
        '      fprintf(stderr, "[gzif-kaslr] WARNING: cleanup failed\\n");\n'
        '    return 0;',
    )
    text = once(
        text,
        '  tracefs_write(tracing_on, "0");\n  if (!found) {',
        '  if (!tracefs_write(tracing_on, "0"))\n'
        '    fprintf(stderr, "[gzif-kaslr] WARNING: failed to stop trace\\n");\n'
        '  if (!found) {',
        "trace stop before final drain",
    )
    text = once(
        text,
        '  tracefs_write(event_enable, "0");\n\n  if (!found) {',
        '  if (!gzif_tracefs_reset(tracing_on, event_enable)) {\n'
        '    fprintf(stderr, "[gzif-kaslr] failed to restore 0/0 controls\\n");\n'
        '    return 0;\n'
        '  }\n\n  if (!found) {',
        "required control restoration before successful return",
    )
    return text


def apply_overlay(engine: Path) -> dict[str, str]:
    """Apply patch to copied engine source after validating BOTH patches.

    Read both originals, validate both transformations, then write. Caller
    must use a fresh disposable copy, never the donor or the generated target.
    """
    orch = engine / "src/00_orchestrator.c"
    trace = engine / "src/01_kernel_base_tracefs.c"
    old_orch = orch.read_text()
    old_trace = trace.read_text()
    new_orch = patch_orchestrator(old_orch)
    new_trace = patch_tracefs(old_trace)
    orch.write_text(new_orch)
    trace.write_text(new_trace)
    return {
        "mode": "ONE_SHOT_GZIF_EXPERIMENTAL_NOT_DEVICE_VALIDATED",
        "attempts": "1",
        "forced_kaslr": "refused",
        "global_trace_truncate": "removed",
        "tracing_baseline": "global tracing_on=0 and event_enable=0 required",
        "restoration": "best-effort on normal return; not guaranteed on SIGKILL",
        "explicit_ack_variable": "GZIF_ONE_SHOT_ACK",
        "device_execution": "NOT_PERFORMED",
    }
