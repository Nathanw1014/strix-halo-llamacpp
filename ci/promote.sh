#!/usr/bin/env bash
# Promote an automated dev build to a curated v0.x release.
#
# The dev pipeline (.github/workflows/dev-build.yml) is the only thing that builds the payload.
# The curated v0.x line has no build of its own: its assets come from a dev release. Doing that
# by hand is how a v-tag ends up shipping a manifest that describes a different payload, and how
# v0.7.1 came to ship `(automated dev build)` with no `validation:` block at all. This makes the
# hand-step one command that refuses to run when the pieces do not match.
#
# What it does:
#   1. resolves the dev-<date>-<short> release for the fork commit you name
#   2. downloads its tarball + MANIFEST.txt and asserts the manifest's `source:` really is that
#      commit, so a mislabelled asset cannot be promoted
#   3. rewrites the manifest's Built/validation lines for the curated release, recording the dev
#      tarball's sha256 so byte-provenance survives the repack
#   4. repacks the tarball with the corrected manifest inside, payload bytes untouched
#   5. uploads both to the v-tag
#
# Nothing is uploaded without --yes; the default prints the plan and the manifest diff.
#
# usage: ci/promote.sh <v-tag> <fork-sha> [--validation FILE] [--yes]
#
#   ci/promote.sh v0.7.2 39817c476 --validation ~/strix-results/v072-validation.txt
#   ci/promote.sh v0.7.2 39817c476 --validation ... --yes
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${PROMOTE_REPO:-Nathanw1014/strix-halo-llamacpp}"
LLAMA_REPO="${LLAMA_REPO:-Nathanw1014/llama.cpp}"

VTAG=""; FORK_SHA=""; VALIDATION_FILE=""; CONFIRM=0
while [ $# -gt 0 ]; do
    case "$1" in
        --validation) VALIDATION_FILE="${2:?--validation needs a file}"; shift 2 ;;
        --yes)        CONFIRM=1; shift ;;
        -h|--help)    sed -n '2,26p' "$0"; exit 0 ;;
        -*)           echo "unknown option: $1" >&2; exit 2 ;;
        *)            if [ -z "$VTAG" ]; then VTAG=$1; elif [ -z "$FORK_SHA" ]; then FORK_SHA=$1;
                      else echo "unexpected argument: $1" >&2; exit 2; fi; shift ;;
    esac
done
[ -n "$VTAG" ] && [ -n "$FORK_SHA" ] || { sed -n '2,26p' "$0"; exit 2; }
command -v gh >/dev/null || { echo "gh CLI is required" >&2; exit 1; }

SHORT=${FORK_SHA:0:7}
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT

# ---- 1. resolve the dev release for this commit -------------------------------------------
echo "== looking for a dev release of $LLAMA_REPO@$SHORT =="
DEVTAG=$(gh release list --repo "$REPO" --limit 60 --json tagName \
    --jq "[.[].tagName | select(startswith(\"dev-\")) | select(endswith(\"-$SHORT\"))][0] // empty")
[ -n "$DEVTAG" ] || {
    echo "no dev release ends in -$SHORT. The curated line only ships payloads the dev" >&2
    echo "pipeline built; trigger a dev build for that commit first." >&2
    exit 1
}
echo "   found $DEVTAG"

# ---- 2. download and verify the manifest describes that commit ----------------------------
gh release download "$DEVTAG" --repo "$REPO" --dir "$WORK" \
    --pattern 'MANIFEST.txt' --pattern 'strix-halo-llamacpp-vulkan-portable.tar.gz'

TARBALL="$WORK/strix-halo-llamacpp-vulkan-portable.tar.gz"
[ -f "$WORK/MANIFEST.txt" ] && [ -f "$TARBALL" ] || { echo "$DEVTAG is missing assets" >&2; exit 1; }

MANIFEST_SHA=$(awk '/^source:/ {print $2; exit}' "$WORK/MANIFEST.txt")
case "$MANIFEST_SHA" in
    "$FORK_SHA"*|*"$SHORT"*) : ;;
    *) echo "REFUSING: $DEVTAG's manifest says source $MANIFEST_SHA, not $FORK_SHA" >&2; exit 1 ;;
esac

# the tarball carries its own copy of the manifest; if the two ever disagree the release is
# already inconsistent and promoting it would launder that
tar -xzOf "$TARBALL" MANIFEST.txt > "$WORK/packed-manifest.txt"
cmp -s "$WORK/MANIFEST.txt" "$WORK/packed-manifest.txt" || {
    echo "REFUSING: $DEVTAG's asset manifest and the one inside its tarball differ" >&2
    diff -u "$WORK/packed-manifest.txt" "$WORK/MANIFEST.txt" >&2 || true
    exit 1
}
echo "== verified: asset and packed manifests agree, source is $MANIFEST_SHA =="

DEV_TAR_SHA=$(sha256sum "$TARBALL" | cut -d' ' -f1)

# ---- 3. rewrite the manifest for the curated release --------------------------------------
{
    printf 'Built %s (curated release %s, promoted from %s)\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$VTAG" "$DEVTAG"
    # everything the dev build recorded about the payload stands; only Built/validation change
    grep -v -e '^Built ' -e '^validation:' -e '^        ' -e '^promoted from:' "$WORK/MANIFEST.txt"
    printf 'promoted from: %s (dev tarball sha256 %s)\n' "$DEVTAG" "$DEV_TAR_SHA"
    if [ -n "$VALIDATION_FILE" ]; then
        [ -f "$VALIDATION_FILE" ] || { echo "validation file does not exist: $VALIDATION_FILE" >&2; exit 1; }
        grep -q '[^[:space:]]' "$VALIDATION_FILE" || { echo "validation file is empty: $VALIDATION_FILE" >&2; exit 1; }
        sed -e :a -e '/^[[:space:]]*$/{$d;N;ba' -e '}' "$VALIDATION_FILE" \
            | awk 'NR==1 {printf "validation: %s\n", $0; next} {printf "        %s\n", $0}'
    else
        echo "validation: NOT RECORDED - promoted without --validation" >&2
        echo "validation: not recorded"
    fi
} > "$WORK/MANIFEST.new"

# ---- 4. repack with the corrected manifest, payload bytes untouched ------------------------
EXTRACT="$WORK/x"; mkdir -p "$EXTRACT"
tar -xzf "$TARBALL" -C "$EXTRACT"
cp "$WORK/MANIFEST.new" "$EXTRACT/MANIFEST.txt"
OUT="$WORK/out"; mkdir -p "$OUT"
tar -C "$EXTRACT" -czf "$OUT/strix-halo-llamacpp-vulkan-portable.tar.gz" \
    vulkan README.md MANIFEST.txt LICENSE THIRD-PARTY-NOTICES.md
cp "$WORK/MANIFEST.new" "$OUT/MANIFEST.txt"

echo
echo "=================== manifest to be published with $VTAG ==================="
cat "$OUT/MANIFEST.txt"
echo "==========================================================================="
echo
echo "payload: $(du -h "$OUT/strix-halo-llamacpp-vulkan-portable.tar.gz" | cut -f1) repacked from $DEVTAG"
echo "         dev tarball sha256 $DEV_TAR_SHA"

# ---- 5. upload -----------------------------------------------------------------------------
if [ "$CONFIRM" != 1 ]; then
    echo
    echo "dry run. Re-run with --yes to upload these two assets to $VTAG."
    exit 0
fi
gh release view "$VTAG" --repo "$REPO" >/dev/null 2>&1 || {
    echo "release $VTAG does not exist; create it first" >&2; exit 1; }
gh release upload "$VTAG" --repo "$REPO" --clobber \
    "$OUT/strix-halo-llamacpp-vulkan-portable.tar.gz" "$OUT/MANIFEST.txt"
echo "== uploaded to $VTAG =="
