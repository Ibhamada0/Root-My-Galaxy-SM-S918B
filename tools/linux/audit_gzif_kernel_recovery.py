#!/usr/bin/env python3
"""Conservative, source-only GZIF BOPE recovery gate; NEVER accesses Android.

A literal-source audit is not a proof of runtime behavior. The known donor
paths are deliberately NO-GO until a reviewed recovery protocol replaces them.
Source drift raises an error rather than silently treating changes as safe.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ORCHESTRATOR = REPO / "targets/zzi8-WIP/brazilian-open-payload-engine/src/00_orchestrator.c"
UMH = REPO / "targets/zzi8-WIP/brazilian-open-payload-engine/src/10_workqueue_umh_root.c"
STATUS = "NO_GO_KERNEL_RECOVERY_UNPROVEN"


def require_unique(source: str, fragment: str, label: str) -> int:
    if source.count(fragment) != 1:
        raise ValueError(f"Source drift ({label}): expected one exact anchor")
    return source[:source.index(fragment)].count("\n") + 1


def between(source: str, start: str, end: str, label: str) -> str:
    require_unique(source, start, label + "/begin")
    require_unique(source, end, label + "/end")
    a = source.index(start)
    b = source.index(end)
    if b <= a:
        raise ValueError(f"Source drift ({label}): unexpected function order")
    return source[a:b]


def evaluate(orchestrator: str, umh: str) -> dict:
    """Return fixed conservative findings for the verified donor source shape."""
    recovery = between(
        orchestrator, "static void recover_ashmem_fops(",
        "static int do_one_attempt_post_trigger(", "fops_fallback",
    )
    require_unique(
        recovery, 'oss_diag_checkpoint("fops-recovery-reboot-required");',
        "fops_reboot_only",
    )
    if any(x in recovery for x in (
        "oss_pipe_rw_write(", "oss_kernel_write(", "restore_ashmem_fops_via_pipe(",
    )):
        raise ValueError("FOPS fallback changed: requires manual recovery review")

    pipe_failure = between(
        orchestrator,
        "  if (!oss_pipe_rw_install(fd, ctx->kernel_base, ctx->payload_base)) {",
        '  oss_diag_checkpoint("pipe-install-ready");',
        "pipe_install_failure",
    )
    require_unique(pipe_failure, "    return 0;", "pipe_failure_return")
    if "restore_ashmem_fops_via_pipe(" in pipe_failure:
        raise ValueError("Pipe error recovery changed: manual review required")

    require_unique(
        orchestrator, "  __atomic_store_n(&ctx->shared->status, ATTEMPT_KERNEL_MUTATED,",
        "kernel_mutation_mark",
    )
    require_unique(
        orchestrator, "  if (!restore_ashmem_fops_via_pipe(",
        "verified_fops_restore_path",
    )
    require_unique(
        orchestrator, '  int rooted = root_umh_install_fd_tracked(',
        "umh_after_fops_restore",
    )
    require_unique(
        orchestrator, '  oss_diag_checkpoint(confirmed ? "fops-restore-confirmed"',
        "fops_restore_confirmation",
    )

    timeout = between(
        umh,
        "  if (trigger_completed == 0) {",
        "  path_restored =\n      oss_pipe_rw_write(fd, static_path_alias, original_guard,", "umh_timeout",
    )
    require_unique(timeout, "    goto out;", "umh_timeout_goto")
    require_unique(
        umh, "  if (path_may_be_changed && trigger_completed != 0) {",
        "skip_static_path_cleanup_on_timeout",
    )
    require_unique(
        umh, "  if (!result && selinux_changed) {",
        "selinux_only_restored_on_failure",
    )
    require_unique(
        umh, "  result = socket_ok && path_restored;",
        "socket_is_not_ksu_success",
    )
    require_unique(
        orchestrator, "if (kernel_state != ATTEMPT_PRE_MUTATION) {",
        "supervisor_waits_after_mutation",
    )
    require_unique(
        orchestrator,
        '"[supervisor] kernel mutation reached; refusing unsafe retry "',
        "unsafe_retry_denied",
    )

    def finding(id: str, src: str, marker: str, why: str, kind: str) -> dict:
        return {
            "id": id,
            "classification": kind,
            "source": src,
            "line": require_unique(
                orchestrator if src == "00_orchestrator.c" else umh,
                marker, id,
            ),
            "interpretation": why,
        }

    findings = [
        finding(
            "FOPS_FALLBACK_LOG_ONLY", "00_orchestrator.c",
            'oss_diag_checkpoint("fops-recovery-reboot-required");',
            "Fallback records reboot-required; it does not restore FOPS.",
            "BLOCKER",
        ),
        finding(
            "PIPE_INSTALL_FAILURE_AFTER_MUTATION", "00_orchestrator.c",
            "  if (!oss_pipe_rw_install(fd, ctx->kernel_base, ctx->payload_base)) {",
            "Pipe installation may fail after mutation without a proven alternate writer.",
            "BLOCKER",
        ),
        finding(
            "UMH_TIMEOUT_STATIC_PATH_PINNED", "10_workqueue_umh_root.c",
            "  if (path_may_be_changed && trigger_completed != 0) {",
            "Timeout skips restoring static UMH path to avoid a late completion race.",
            "BLOCKER",
        ),
        finding(
            "SELINUX_SUCCESS_LIFETIME_GAP", "10_workqueue_umh_root.c",
            "  if (!result && selinux_changed) {",
            "Successful socket path defers enforcing restoration to separate userland work.",
            "BLOCKER",
        ),
        finding(
            "FOPS_PIPE_READBACK", "00_orchestrator.c",
            '  oss_diag_checkpoint(confirmed ? "fops-restore-confirmed"',
            "Normal pipe path performs readback confirmation; it cannot cover pipe failure.",
            "PARTIAL_GUARD",
        ),
        finding(
            "NO_RETRY_AFTER_MUTATION", "00_orchestrator.c",
            '"[supervisor] kernel mutation reached; refusing unsafe retry "',
            "Prevents an unsafe retry but does not repair kernel state.",
            "PARTIAL_GUARD",
        ),
    ]
    return {
        "target": "SM-S918N/S918NKSU8GZIF",
        "status": STATUS,
        "device_io": False,
        "source_only": True,
        "blockers": sum(f["classification"] == "BLOCKER" for f in findings),
        "findings": findings,
        "limitations": [
            "Literal C source anchors cannot validate actual kernel control flow.",
            "Recovery on kernel panic, SIGKILL, or protected module refusal is unproven.",
            "Do not run BOPE full mutation based on this source-only report.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable audit")
    args = parser.parse_args()
    try:
        result = evaluate(
            ORCHESTRATOR.read_text(),
            UMH.read_text(),
        )
    except (OSError, ValueError) as error:
        print(json.dumps({
            "status": "SOURCE_DRIFT_REVIEW_REQUIRED",
            "error": str(error),
            "device_io": False,
        }, indent=2))
        return 3

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"[{result['status']}] {result['target']}")
        for item in result["findings"]:
            print(f"  {item['classification']}: {item['id']} "
                  f"at {item['source']}:{item['line']}")
        print("Source-only recovery gate: NOT APPROVED FOR DEVICE MUTATION")
    return 2  # NO-GO is the expected audit result, not a Python/test failure.


if __name__ == "__main__":
    raise SystemExit(main())
