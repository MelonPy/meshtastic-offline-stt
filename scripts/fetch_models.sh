#!/usr/bin/env bash
# Download every model listed in configs/models.lock.json and verify its SHA256.
# Fails (exit 1) on any checksum or size mismatch; a mismatching file is deleted.
#
#   scripts/fetch_models.sh                 # all models
#   scripts/fetch_models.sh whisper-tiny vosk-small-fr-0.22   # selected ids
#   scripts/fetch_models.sh --verify        # only re-check files already on disk
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="$ROOT/configs/models.lock.json"
MODELS="$ROOT/models"
VERIFY_ONLY=0
if [ "${1:-}" = "--verify" ]; then VERIFY_ONLY=1; shift; fi

command -v sha256sum >/dev/null || { echo "sha256sum not found" >&2; exit 1; }
command -v curl >/dev/null || { echo "curl not found" >&2; exit 1; }

# Emit: id <TAB> path <TAB> url <TAB> size <TAB> sha256 <TAB> unpack
python3 - "$LOCK" "$@" <<'PY' > "${TMPDIR:-/tmp}/fetch_models.$$"
import json, sys
lock, wanted = sys.argv[1], set(sys.argv[2:])
models = json.load(open(lock))["models"]
known = {m["id"] for m in models}
unknown = wanted - known
if unknown:
    sys.exit(f"unknown model id(s): {', '.join(sorted(unknown))}")
for m in models:
    if wanted and m["id"] not in wanted:
        continue
    for f in m["files"]:
        print("\t".join([m["id"], f["path"], f["url"], str(f["size"]), f["sha256"], m.get("unpack", "")]))
PY
LIST="${TMPDIR:-/tmp}/fetch_models.$$"
trap 'rm -f "$LIST"' EXIT

fail=0
while IFS=$'\t' read -r id path url size sha unpack; do
  dest="$MODELS/$id/$path"
  mkdir -p "$(dirname "$dest")"
  if [ ! -f "$dest" ]; then
    if [ "$VERIFY_ONLY" = 1 ]; then echo "MISSING  $id/$path"; fail=1; continue; fi
    echo "GET      $id/$path"
    curl -fL --retry 4 --retry-delay 2 -sS -o "$dest.part" "$url"
    mv "$dest.part" "$dest"
  fi
  actual_size=$(stat -c %s "$dest")
  actual_sha=$(sha256sum "$dest" | cut -d' ' -f1)
  if [ "$actual_size" != "$size" ] || [ "$actual_sha" != "$sha" ]; then
    echo "MISMATCH $id/$path" >&2
    echo "  expected sha256=$sha size=$size" >&2
    echo "  got      sha256=$actual_sha size=$actual_size" >&2
    rm -f "$dest"
    fail=1
    continue
  fi
  echo "OK       $id/$path  sha256=$actual_sha"
  if [ "$unpack" = "zip" ]; then
    # Extract once from the verified archive and record the hash of every extracted
    # file, so a later edit of the unpacked model is caught too.
    if [ ! -f "$MODELS/$id/.unpacked.sha256" ]; then
      rm -rf "$MODELS/$id/${path%.zip}"
      (cd "$MODELS/$id" && python3 -m zipfile -e "$path" . \
        && find "${path%.zip}" -type f | sort | xargs -d '\n' sha256sum > .unpacked.sha256)
    fi
    if ! (cd "$MODELS/$id" && sha256sum --quiet -c .unpacked.sha256); then
      echo "MISMATCH $id: unpacked files differ from the verified archive" >&2
      echo "  fix: rm -rf '$MODELS/$id/${path%.zip}' '$MODELS/$id/.unpacked.sha256' and re-run" >&2
      fail=1
    fi
  fi
done < "$LIST"

if [ "$fail" != 0 ]; then
  echo "ERROR: one or more model files failed verification" >&2
  exit 1
fi
echo "All model files verified."
