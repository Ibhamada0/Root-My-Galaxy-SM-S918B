/*
 * Read-only, non-root native Android execution smoke check for S918NKSU8GZIF.
 * NO BOPE, KernelSU, tracefs writes, kernel probes, or privilege escalation.
 * Compiled separately from the exploit; prints no device identifiers/serials.
 */
#include <sys/system_properties.h>
#include <sys/utsname.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define GZIF_KERNEL "5.15.197-android13-8-34343818-abS918NKSU8GZIF"
#define GZIF_VERSION "#1 SMP PREEMPT Mon Sep 28 01:56:16 UTC 2026"
#define GZIF_FINGERPRINT \
  "samsung/dm3qksx/dm3q:17/CP2A.260605.016/S918NKSU8GZIF:user/release-keys"

static int compare_text(const char *label, const char *actual,
                        const char *expected) {
    int equal = strcmp(actual, expected) == 0;
    printf("%s: %s\n", label, equal ? "MATCH" : "MISMATCH");
    return equal ? 0 : 1;
}

static int compare_property(const char *name, const char *expected) {
    char actual[PROP_VALUE_MAX] = {0};
    int length = __system_property_get(name, actual);
    if (length <= 0) {
        printf("%s: UNAVAILABLE\n", name);
        return 1;
    }
    return compare_text(name, actual, expected);
}

static int selinux_readonly(void) {
    int fd = open("/sys/fs/selinux/enforce", O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        puts("SELinux: UNAVAILABLE (not changed)");
        return 1;
    }
    char status = '\0';
    ssize_t got = read(fd, &status, 1);
    close(fd);
    if (got != 1) {
        puts("SELinux: UNAVAILABLE (not changed)");
        return 1;
    }
    printf("SELinux: %s\n",
           status == '1' ? "Enforcing" :
           status == '0' ? "Permissive" : "UNKNOWN");
    return status == '1' ? 0 : 1;
}

int main(void) {
    struct utsname uts = {0};
    int failures = 0;
    puts("GZIF_NATIVE_SMOKE_V1");
    puts("Mode: read-only native Android process; no exploit invoked");
    if (uname(&uts) != 0) {
        perror("uname");
        return 2;
    }
    failures += compare_text("Architecture", uts.machine, "aarch64");
    failures += compare_text("Kernel release", uts.release, GZIF_KERNEL);
    failures += compare_text("Kernel version", uts.version, GZIF_VERSION);
    failures += compare_property("ro.product.model", "SM-S918N");
    failures += compare_property("ro.product.device", "dm3q");
    failures += compare_property("ro.build.version.incremental", "S918NKSU8GZIF");
    failures += compare_property("ro.build.fingerprint", GZIF_FINGERPRINT);
    failures += selinux_readonly();
    printf("Execution UID: %ld\n", (long)geteuid());
    if (geteuid() == 0) {
        puts("Unexpected root execution: FAIL");
        failures++;
    }
    printf("GZIF_NATIVE_SMOKE_RESULT: %s\n", failures ? "FAIL" : "PASS");
    return failures ? 1 : 0;
}
