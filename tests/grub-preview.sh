#!/usr/bin/env bash
# Boot a composed GRUB theme in QEMU (UEFI) and save a screenshot, without
# root and without touching the machine's own GRUB.
#
#   tests/grub-preview.sh THEME_DIR WIDTH HEIGHT OUT.png [KEYS]
#
# KEYS: optional QEMU key names sent before the picture (e.g. "down down").
# Needs grub-mkstandalone (x86_64-efi), qemu-system-x86_64, OVMF, python3
# with Pillow for the PNG.
set -euo pipefail
THEME=$(cd "$1" && pwd); W=$2; H=$3; OUT=$4; KEYS=${5:-}
T=$(mktemp -d "${TMPDIR:-/tmp}/nirusplash-grub.XXXXXX")
trap 'kill "$(cat "$T/pid" 2>/dev/null)" 2>/dev/null || :; rm -rf "$T"' EXIT
font=$(basename "$(ls "$THEME"/*.pf2 | head -1)")
mkdir -p "$T/mem/boot/grub/themes" "$T/esp/EFI/BOOT"
cp -r "$THEME" "$T/mem/boot/grub/themes/nirux"
cat > "$T/mem/boot/grub/grub.cfg" <<EOF
insmod all_video
insmod gfxterm
insmod gfxmenu
insmod png
loadfont (memdisk)/boot/grub/themes/nirux/$font
set gfxmode=${W}x${H},auto
terminal_output gfxterm
set theme=(memdisk)/boot/grub/themes/nirux/theme.txt
set timeout_style=menu
set timeout=${PREVIEW_TIMEOUT:-3}
menuentry 'Debian GNU/Linux' { true }
menuentry 'Debian GNU/Linux, with Linux 7.2.12+deb13-amd64' { true }
menuentry 'Debian GNU/Linux, with Linux 7.2.12+deb13-amd64 (recovery mode)' { true }
menuentry 'Debian GNU/Linux, with Linux 7.2.11+deb13-amd64' { true }
menuentry 'Debian GNU/Linux, with Linux 7.2.11+deb13-amd64 (recovery mode)' { true }
menuentry 'UEFI Firmware Settings' { fwsetup }
EOF
# shellcheck disable=SC2046
(cd "$T/mem" && grub-mkstandalone -O x86_64-efi -o "$T/esp/EFI/BOOT/BOOTX64.EFI" \
  --modules="part_gpt fat all_video gfxterm gfxmenu png font memdisk" "boot/grub/grub.cfg=boot/grub/grub.cfg" \
  $(cd "$T/mem" && find boot/grub/themes -type f -printf '%p=%p ') )
cp /usr/share/OVMF/OVMF_VARS_4M.fd "$T/vars.fd"
accel=tcg; [ -w /dev/kvm ] && accel=kvm
qemu-system-x86_64 -machine q35,accel=$accel -m 512 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file="$T/vars.fd" \
  -drive format=raw,file=fat:rw:"$T/esp" \
  -device VGA,edid=on,xres="$W",yres="$H" -display none \
  -qmp unix:"$T/qmp",server=on,wait=off -daemonize -pidfile "$T/pid"
python3 - "$T/qmp" "$T/shot.ppm" "$OUT" "$KEYS" "${PREVIEW_WAIT:-9}" <<'EOF'
import json, socket, sys, time
from PIL import Image
sock, ppm, out, keys, wait = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5])
s = socket.socket(socket.AF_UNIX)
for _ in range(50):
    try:
        s.connect(sock); break
    except OSError:
        time.sleep(0.2)
f = s.makefile("rw")
def cmd(c, **a):
    f.write(json.dumps({"execute": c, "arguments": a} if a else {"execute": c}) + "\n"); f.flush()
    while True:
        r = json.loads(f.readline())
        if "return" in r or "error" in r:
            return r
f.readline()
cmd("qmp_capabilities")
time.sleep(wait)
for k in keys.split():
    cmd("send-key", keys=[{"type": "qcode", "data": k}]); time.sleep(0.4)
time.sleep(1)
print(cmd("screendump", filename=ppm))
time.sleep(0.5)
Image.open(ppm).save(out)
EOF
echo "saved $OUT"
