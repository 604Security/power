#!/usr/bin/env bash
# install.sh: install (or update) power as a read-only copy, after showing you exactly what changes.
# Your installed copy never changes by itself: not when the repo changes, only when you run this and say yes.
#   ./install.sh              -> ~/.local/bin/power
#   TARGET=/some/dir ./install.sh
set -e
SRC="$(cd "$(dirname "$0")" && pwd)/power"
DEST="${TARGET:-$HOME/.local/bin}/power"
if [ -t 1 ] || [ -n "$POWER_COLOR" ]; then GREEN=$'\e[1;32m' BLUE=$'\e[1;34m' YELLOW=$'\e[1;33m' OFF=$'\e[0m'; fi

echo "${BLUE}[*]${OFF} power $(sha256sum "$SRC" | cut -c1-16)…  ->  $DEST"
if [ -f "$DEST" ] && cmp -s "$SRC" "$DEST"; then
  echo "${GREEN}[+]${OFF} Already up to date. Nothing to do."
  exit 0
fi
if [ -f "$DEST" ]; then
  echo "${YELLOW}[!]${OFF} These lines would change (- yours now, + new):"
  diff -u "$DEST" "$SRC" | tail -n +3 || true
else
  echo "${YELLOW}[!]${OFF} First install. Read the script before you trust it: $SRC"
fi
read -r -p "Install this? [y/N] " ok
[ "$ok" = y ] || [ "$ok" = Y ] || { echo "${YELLOW}[!]${OFF} Not installed."; exit 1; }
mkdir -p "$(dirname "$DEST")"
install -m 555 "$SRC" "$DEST"
echo "${GREEN}[+]${OFF} Installed (read-only). Fingerprint: $(sha256sum "$DEST" | cut -c1-16)…"
