#!/usr/bin/env bash
# Build the release: dist/nirusplash (one file, the installer with its
# pictures' raw material appended) and dist/SHA256SUMS.
#
#   tools/build-release.sh [FONT_DIR]
#
# Needs python3 with Pillow, grub-mkfont and the DejaVu fonts.
set -euo pipefail
cd "$(dirname "$0")/.."
FONTS=${1:-/usr/share/fonts/truetype/dejavu}
VERSION=$(cat VERSION)
rm -rf build dist
mkdir -p build/payload/lib build/grub-fonts dist
python3 tools/build-assets.py "$FONTS/DejaVuSansMono.ttf" build/assets
for s in $(seq 12 40); do
  grub-mkfont -s "$s" -n "NIRUX Mono" -r 0x20-0x7E -r 0xA0-0xFF -r 0x2022-0x2022 \
    -r 0x2190-0x2193 -r 0x2500-0x257F -o "build/grub-fonts/nirux-mono-$s.pf2" "$FONTS/DejaVuSansMono.ttf"
done
cp lib/compose.py lib/nirux.script.in build/payload/lib/
printf '%s\n' "$VERSION" > build/payload/lib/VERSION
cp -r build/assets build/payload/assets
cp -r build/grub-fonts build/payload/grub-fonts
cp LICENSE FONTS.md build/payload/
sed "s/^VERSION=.*/VERSION=$VERSION/" nirusplash > dist/nirusplash
printf '\n__PAYLOAD__\n' >> dist/nirusplash
# Reproducible: fixed owner, order and times.
tar --sort=name --owner=0 --group=0 --numeric-owner --mtime='2026-01-01 00:00Z' \
  -C build/payload -cf - . | xz -9e -T1 | base64 -w 76 >> dist/nirusplash
chmod 755 dist/nirusplash
(cd dist && sha256sum nirusplash > SHA256SUMS)
dist/nirusplash --version
ls -l dist
