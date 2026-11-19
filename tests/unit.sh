#!/usr/bin/env bash
# Quick checks without root: the composer for several screens and palettes,
# the GRUB settings block, and the release file.
#
#   tests/unit.sh        (after tools/build-release.sh)
set -euo pipefail
cd "$(dirname "$0")/.."
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

# 1. Every common screen gets a theme that fits on it.
for size in 1024x768 1280x800 1366x768 1920x1080 1920x1200 2560x1440 2560x1600 2880x1800 3840x2160; do
  w=${size%x*} h=${size#*x}
  python3 -I lib/compose.py --assets build/assets --grub-fonts build/grub-fonts --out "$T/$size" \
    --width "$w" --height "$h" > "$T/$size.json" || fail "compose $size"
  for f in theme.txt banner.png tagline.png select_w.png; do [ -s "$T/$size/grub/$f" ] || fail "$size: no grub/$f"; done
  for f in nirux.plymouth nirux.script hash.png prompt.png fail.png working.png; do [ -s "$T/$size/plymouth/$f" ] || fail "$size: no plymouth/$f"; done
  ! grep -q '@[A-Z_]*@' "$T/$size/plymouth/nirux.script" || fail "$size: unfilled template value"
  python3 - "$T/$size" "$w" "$h" <<'EOF' || fail "$size: does not fit"
import re, struct, sys
d, w, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
t = open(f"{d}/grub/theme.txt").read()
def png(p):
    b = open(p, "rb").read(24)
    return struct.unpack(">II", b[16:24])
bw, bh = png(f"{d}/grub/banner.png")
assert bw <= w * 0.62 and bh <= h * 0.3, (bw, bh)
for m in re.finditer(r"top = (\d+)", t):
    assert int(m.group(1)) < h, m.group(0)
menu = re.search(r"\+ boot_menu \{.*?top = (\d+).*?height = (\d+)", t, re.S)
assert int(menu.group(1)) + int(menu.group(2)) < h, "menu below the screen"
EOF
done

# 2. A dim accent falls back to the text colour (as in nirulock).
python3 -I - <<'EOF' || fail 'banner colour rule'
import sys
sys.path.insert(0, "lib")
import compose
assert compose.banner_colour((0x5a, 0x5a, 0x60), (0xe5, 0xe5, 0xe5), (0, 0, 0)) == (0xe5, 0xe5, 0xe5)
assert compose.banner_colour((0x7f, 0xbf, 0x6a), (0xe5, 0xe5, 0xe5), (0, 0, 0)) == (0x7f, 0xbf, 0x6a)
EOF

# 3. Bad input is refused.
! python3 -I lib/compose.py --assets build/assets --out "$T/x" --width 1920 --height 1080 --focus nope 2>/dev/null ||
  fail 'a bad colour was accepted'

# 4. The GRUB block: added once, only the missing words, removed cleanly.
G=$T/grub-default
cat > "$G" <<'EOF'
GRUB_DEFAULT=0
GRUB_TIMEOUT=5
GRUB_CMDLINE_LINUX_DEFAULT="quiet threadirqs"
EOF
cp "$G" "$G.orig"
cat > "$T/block.sh" <<EOF
set -euo pipefail
GRUB_DEFAULT_FILE=$G
NIRUSPLASH_STATE_DIR=$T/state
EOF
# shellcheck disable=SC2016
sed -n '/^MARK_BEGIN=/,/^MARK_END=/p; /^strip_block()/,/^}/p; /^cmdline_without_block()/,/^}/p; /^grub_block()/,/^}/p' nirusplash >> "$T/block.sh"
cat >> "$T/block.sh" <<'EOF'
say() { printf '%s\n' "$*"; }
THEME_DIR=/boot/grub/themes/nirux TIMEOUT=3
b=$(grub_block 1920x1200 yes nirux-mono-22.pf2)
{ strip_block "$GRUB_DEFAULT_FILE"; say "$b"; } > "$GRUB_DEFAULT_FILE.new"; mv "$GRUB_DEFAULT_FILE.new" "$GRUB_DEFAULT_FILE"
b=$(grub_block 1920x1200 yes nirux-mono-22.pf2)
{ strip_block "$GRUB_DEFAULT_FILE"; say "$b"; } > "$GRUB_DEFAULT_FILE.new"; mv "$GRUB_DEFAULT_FILE.new" "$GRUB_DEFAULT_FILE"
( set +u; . "$GRUB_DEFAULT_FILE"; printf '%s|%s|%s|%s\n' "$GRUB_CMDLINE_LINUX_DEFAULT" "$GRUB_TIMEOUT" "$GRUB_THEME" "$GRUB_DISABLE_SUBMENU" )
strip_block "$GRUB_DEFAULT_FILE" > "$GRUB_DEFAULT_FILE.stripped"
EOF
out=$(bash "$T/block.sh")
[ "$out" = 'quiet threadirqs splash|3|/boot/grub/themes/nirux/theme.txt|y' ] || fail "grub block: $out"
[ "$(grep -c '^# >>> nirusplash' "$G")" = 1 ] || fail 'the block was added twice'
cmp -s "$G.stripped" "$G.orig" || fail 'removing the block does not give the original back'

# 5. The release file unpacks and composes.
if [ -x dist/nirusplash ]; then
  dist/nirusplash --version | grep -qx "nirusplash $(cat VERSION)" || fail 'release version'
  list=$(sed '1,/^__PAYLOAD__$/d' dist/nirusplash | base64 -d | tar -tJ)
  case "$list" in *lib/compose.py*) ;; *) fail 'payload' ;; esac
fi
echo 'unit: ok'
