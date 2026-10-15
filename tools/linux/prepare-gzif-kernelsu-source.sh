#!/usr/bin/env bash
# Fetch and pin the upstream KernelSU Next v3.4.0 sources for the
# SM-S918N/GZIF port. No module build, patch, signing, adb or load.
set -euo pipefail

tag=v3.4.0
upstream=https://github.com/KernelSU-Next/KernelSU-Next.git
base="${GZIF_KSU_SOURCE_ROOT:-$HOME/rmg-firmware/gzif-kernelsu-source}"
dest="$base/KernelSU-Next-$tag"

if ! command -v git >/dev/null 2>&1; then
  echo "[ERROR] git required" >&2
  exit 2
fi
if ! command -v sha256sum >/dev/null 2>&1; then
  echo "[ERROR] sha256sum required" >&2
  exit 2
fi
mkdir -p -- "$base"
if [[ ! -e "$dest" ]]; then
  echo "Cloning exact upstream $tag into $dest"
  git clone --quiet --depth 1 --branch "$tag" -- "$upstream" "$dest"
elif [[ ! -d "$dest/.git" ]]; then
  echo "[ERROR] Existing destination is not a Git checkout: $dest" >&2
  exit 2
fi

actual_tag="$(git -C "$dest" describe --tags --exact-match HEAD 2>/dev/null || true)"
if [[ "$actual_tag" != "$tag" ]]; then
  echo "[ERROR] Source checkout not on exact upstream tag $tag" >&2
  exit 2
fi

commit="$(git -C "$dest" rev-parse HEAD)"
# v3.4.0 is tagged at upstream's release commit 1a879d6.
if [[ "$commit" != 1a879d6* ]]; then
  echo "[ERROR] Upstream v3.4.0 tag resolved unexpectedly: $commit" >&2
  exit 2
fi
if [[ ! -f "$dest/kernel/Makefile" || ! -f "$dest/userspace/ksud/Cargo.toml" ]]; then
  echo "[ERROR] Upstream kernel/ksud sources are incomplete" >&2
  exit 2
fi

echo "GZIF_KERNELSU_SOURCE_PREPARED"
echo "Source: $upstream"
echo "Tag: $tag"
echo "Commit: $commit"
echo "Directory: $dest"
sha256sum "$dest/kernel/Makefile" "$dest/userspace/ksud/Cargo.toml"
echo "Next required input: matched GZIF kernel/DDK build source/config."
echo "No kernelsu.ko has been built for SM-S918N/GZIF; do not deploy."
