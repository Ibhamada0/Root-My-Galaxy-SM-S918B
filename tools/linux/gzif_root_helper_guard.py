#!/usr/bin/env python3
"""GZIF-only root-helper safety overlay for DISPOSABLE NDK build copies.

Adds a best-effort 180-second SELinux restoration fuse and a hard
temporary-root socket lifetime. It cannot guarantee recovery on kernel
panic, missing root UMH, SIGKILL of both processes, or broken SELinux.
The original ZZI8 donor and generated GZIF source remain untouched.
"""
from __future__ import annotations

from pathlib import Path

GZIF_FUSE_SECONDS = 180


def replace_once(source: str, old: str, new: str, reason: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"GZIF root helper unexpected source layout ({reason})")
    return source.replace(old, new, 1)


def patch_gzif_root_helper(source: str) -> str:
    # This is an overlay, not an edit to the shared donor. Reject a helper
    # that has changed substantially or that has already been patched.
    if "gzif-selinux-fuse" in source:
        raise ValueError("GZIF root helper already contains a fuse")
    for required in (
        '#define BOOTSTRAP_SOCK_PATH "/data/local/tmp/temp_su.sock"',
        '#define KSU_LOADER_PATH "/data/local/tmp/ksud-selected"',
        "static int restore_selinux_enforcing(void) {",
        "static int daemon_main(void) {",
        "static int binfmt_umh_main(int argc, char **argv) {",
        "return daemon_main();",
        "  _exit(daemon_main());",
    ):
        if required not in source:
            raise ValueError(f"GZIF root helper missing required contract: {required}")

    source = replace_once(
        source,
        "#include <termios.h>\n",
        "#include <termios.h>\n#include <time.h>\n",
        "monotonic deadline include",
    )
    source = replace_once(
        source,
        "static int daemon_main(void) {",
        r"""/* GZIF-only safety fuse for temporary root via UMH.
 * A watcher separate from the root daemon attempts to restore SELinux
 * even if the daemon blocks or is killed; neither child can restore
 * kernel state during panic, power loss, or global process termination.
 * All deadlines are CLOCK_MONOTONIC, independent of wall clock changes.
 */
#define GZIF_ROOT_FUSE_SECONDS 180U
#define GZIF_ROOT_FUSE_MS (GZIF_ROOT_FUSE_SECONDS * 1000ULL)

static uint64_t gzif_monotonic_ms(void) {
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return 0;
  return (uint64_t)ts.tv_sec * 1000ULL +
         (uint64_t)ts.tv_nsec / 1000000ULL;
}

static void gzif_sleep_until(uint64_t deadline_ms) {
  for (;;) {
    uint64_t now_ms = gzif_monotonic_ms();
    if (!now_ms || now_ms >= deadline_ms) break;
    uint64_t remaining = deadline_ms - now_ms;
    struct timespec delay = {
        .tv_sec = (time_t)(remaining / 1000ULL),
        .tv_nsec = (long)(remaining % 1000ULL) * 1000000L,
    };
    while (nanosleep(&delay, &delay) < 0 && errno == EINTR) {
    }
  }
}

static int gzif_start_selinux_watcher(uint64_t deadline_ms) {
  pid_t watcher = fork();
  if (watcher < 0) return 0;
  if (watcher == 0) {
    /* Avoid inheriting a parent-death signal from the UMH bootstrap.
     * This is best effort; fatal signal delivery is still possible.
     */
    prctl(PR_SET_PDEATHSIG, 0);
    prctl(PR_SET_NAME, "gzif-selinux-fuse", 0, 0, 0);
    gzif_sleep_until(deadline_ms);
    int restored = restore_selinux_enforcing();
    dprintf(STDERR_FILENO,
            "stage=gzif-selinux-fuse watchdog enforcing=%d\n", restored);
    _exit(restored ? 0 : 133);
  }
  return 1;
}

static int daemon_main(void) {""",
        "GZIF root fuse declaration",
    )

    source = replace_once(
        source,
        """static int daemon_main(void) {
  signal(SIGPIPE, SIG_IGN);
  set_root_env();

  int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);""",
        r"""static int daemon_main(void) {
  signal(SIGPIPE, SIG_IGN);
  set_root_env();

  /* Watchdog starts before opening the privileged socket. If it
   * cannot start, restore SELinux now and do not serve root requests.
   */
  uint64_t started_ms = gzif_monotonic_ms();
  if (geteuid() != 0 || !started_ms) {
    (void)restore_selinux_enforcing();
    return 131;
  }
  uint64_t deadline_ms = started_ms + GZIF_ROOT_FUSE_MS;
  if (!gzif_start_selinux_watcher(deadline_ms)) {
    (void)restore_selinux_enforcing();
    return 132;
  }
  dprintf(STDERR_FILENO,
          "stage=gzif-selinux-fuse armed timeout_sec=%u\n",
          GZIF_ROOT_FUSE_SECONDS);

  int fd = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);""",
        "arm watchdog before privileged temporary-root listener",
    )

    original_loop = """  for (;;) {
    int conn = accept4(fd, NULL, NULL, SOCK_CLOEXEC);
    if (conn < 0 && errno == EINTR) {
      continue;
    }
    if (conn < 0) {
      sleep(1);
      continue;
    }

    pid_t pid = fork();
    if (pid == 0) {
      close(fd);
      serve_one(conn);
      close(conn);
      _exit(0);
    }
    close(conn);
    while (waitpid(-1, NULL, WNOHANG) > 0) {
    }
  }
}"""
    new_loop = r"""  for (;;) {
    uint64_t now_ms = gzif_monotonic_ms();
    if (!now_ms || now_ms >= deadline_ms) break;
    uint64_t remaining_ms = deadline_ms - now_ms;
    struct pollfd pfd = {.fd = fd, .events = POLLIN};
    int ready = poll(&pfd, 1, (int)(remaining_ms > 1000 ? 1000 : remaining_ms));
    if (ready < 0 && errno == EINTR) continue;
    if (ready <= 0) continue;
    /* The callback must NOT accept new sessions after the fuse expires. */
    if (gzif_monotonic_ms() >= deadline_ms) break;
    int conn = accept4(fd, NULL, NULL, SOCK_CLOEXEC);
    if (conn < 0 && (errno == EINTR || errno == EAGAIN)) continue;
    if (conn < 0) continue;

    pid_t pid = fork();
    if (pid == 0) {
      close(fd);
      /* This child may still be in a late-load request at the
       * deadline. The independent fuse will restore enforcing.
       */
      serve_one(conn);
      close(conn);
      _exit(0);
    }
    close(conn);
    while (waitpid(-1, NULL, WNOHANG) > 0) {
    }
  }
  close(fd);
  unlink(BOOTSTRAP_SOCK_PATH);
  int restored = restore_selinux_enforcing();
  dprintf(STDERR_FILENO,
          "stage=gzif-selinux-fuse daemon-expired enforcing=%d\n",
          restored);
  return restored ? 0 : 134;
}"""
    source = replace_once(
        source, original_loop, new_loop,
        "bounded temporary-root socket lifetime",
    )
    # The listener remains blocking. Poll limits the wait for incoming
    # requests. Do not mark the accepted connection SOCK_NONBLOCK: the
    # original read_full/recvmsg protocol assumes blocking sockets.
    source = replace_once(
        source,
        "  if (fd < 0) {\n    return 1;\n  }\n\n  struct sockaddr_un sun;",
        "  if (fd < 0) {\n    (void)restore_selinux_enforcing();\n    return 1;\n  }\n\n  struct sockaddr_un sun;",
        "immediate SELinux cleanup on socket creation failure",
    )
    source = replace_once(
        source,
        "    close(fd);\n    return 1;\n  }\n  chmod(BOOTSTRAP_SOCK_PATH, 0666);",
        "    close(fd);\n    (void)restore_selinux_enforcing();\n    return 1;\n  }\n  chmod(BOOTSTRAP_SOCK_PATH, 0666);",
        "immediate SELinux cleanup on bind/listen failure",
    )
    # Fail closed if the temporary-root listener cannot become reachable.
    # The original helper ignored chmod errors and could leave SELinux
    # permissive while waiting for a socket the client cannot use.
    source = replace_once(
        source,
        "  chmod(BOOTSTRAP_SOCK_PATH, 0666);\n\n  for (;;) {",
        "  if (chmod(BOOTSTRAP_SOCK_PATH, 0666) != 0) {\n"
        "    close(fd);\n"
        "    unlink(BOOTSTRAP_SOCK_PATH);\n"
        "    (void)restore_selinux_enforcing();\n"
        "    return 135;\n"
        "  }\n\n  for (;;) {",
        "cleanup on temporary-root socket chmod failure",
    )
    # Close four deterministic pre-watchdog UMH failure windows.
    # These are only best-effort writes by a running root process;
    # SIGKILL/panic and failures of the SELinux interface still remain.
    source = replace_once(
        source,
        "      !parse_binfmt_uid(argv[3], &client_uid)) {\n    return 124;\n  }\n  allowed_client_uid = client_uid;",
        "      !parse_binfmt_uid(argv[3], &client_uid)) {\n    if (geteuid() == 0) (void)restore_selinux_enforcing();\n    return 124;\n  }\n  allowed_client_uid = client_uid;",
        "best-effort enforcing restoration on invalid UMH invocation",
    )
    source = replace_once(
        source,
        "      getuid() != 0 || geteuid() != 0 || getgid() != 0 || getegid() != 0) {\n    return 125;\n  }\n  pid_t daemon = fork();",
        "      getuid() != 0 || geteuid() != 0 || getgid() != 0 || getegid() != 0) {\n    (void)restore_selinux_enforcing();\n    return 125;\n  }\n  pid_t daemon = fork();",
        "best-effort enforcing restoration on UMH credential failure",
    )
    source = replace_once(
        source,
        "  if (daemon < 0) {\n    return 126;\n  }\n  if (daemon > 0)",
        "  if (daemon < 0) {\n    (void)restore_selinux_enforcing();\n    return 126;\n  }\n  if (daemon > 0)",
        "best-effort enforcing restoration on root daemon fork failure",
    )
    source = replace_once(
        source,
        "  if (setsid() < 0) {\n    _exit(127);\n  }\n  prctl(PR_SET_NAME, \"cve43499-root\"",
        "  if (setsid() < 0) {\n    (void)restore_selinux_enforcing();\n    _exit(127);\n  }\n  prctl(PR_SET_NAME, \"cve43499-root\"",
        "best-effort enforcing restoration on root daemon setsid failure",
    )
    return source


def apply_helper_overlay(helper_directory: Path) -> dict[str, object]:
    path = helper_directory / "su_daemon.c"
    original = path.read_text()
    updated = patch_gzif_root_helper(original)
    path.write_text(updated)
    return {
        "mode": "GZIF_TEMP_ROOT_SELINUX_FUSE_HOST_SOURCE_ONLY",
        "timeout_seconds": GZIF_FUSE_SECONDS,
        "donor_source_modified": False,
        "independent_watcher": "best-effort, not a kernel-level guarantee",
        "temporary_root_socket": "bounded to fuse deadline",
        "pre_watchdog_failure_cleanup": "four UMH early-return paths attempt enforcing restoration",
        "failure_risks": [
            "Kernel panic/power loss cannot be recovered by userspace",
            "Signal termination of watchdog and daemon cannot be prevented",
            "UMH can fail before daemon/watchdog is created",
            "Enforcing restored during an unfinished late-load may make it fail",
            "BOPE static usermode helper and kernel-memory restoration remain independent risks",
        ],
        "device_execution": "NOT_PERFORMED",
    }
