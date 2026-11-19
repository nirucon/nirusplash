#!/usr/bin/env bash
# Run a composed Plymouth theme in a Debian container with Plymouth's X11
# renderer in a private Xvfb, and save screenshots of the typing, the
# password prompt, a wrong password and the second try.
#
#   tests/plymouth-preview.sh THEME_DIR WIDTH HEIGHT OUTDIR
#
# Needs docker. Nothing runs on the host's display.
set -euo pipefail
THEME=$(cd "$1" && pwd); W=$2; H=$3; OUT=$4
mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd)
IMAGE=nirusplash-preview:2
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker build -q -t "$IMAGE" - <<'EOF' >/dev/null
FROM debian:trixie
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    plymouth plymouth-x11 xvfb x11-apps imagemagick procps xdotool >/dev/null && rm -rf /var/lib/apt/lists/*
EOF
fi
docker run --rm -t -v "$THEME:/theme:ro" -v "$OUT:/out" -e W="$W" -e H="$H" "$IMAGE" bash -c '
set -u
cp -r /theme /usr/share/plymouth/themes/nirux
plymouth-set-default-theme nirux
mkdir -p /run/plymouth
Xvfb :7 -screen 0 ${W}x${H}x24 -nolisten tcp >/dev/null 2>&1 &
sleep 1
export DISPLAY=:7
plymouthd --no-daemon --debug --debug-file=/out/plymouthd.log --mode=boot --kernel-command-line="quiet splash" --tty=$(tty) >/dev/null 2>&1 &
sleep 1.5
plymouth show-splash
shot() { sleep "$1"; xwd -root -silent | convert xwd:- /out/$2.png; }
keys() { xdotool search --sync --onlyvisible --class . windowfocus --sync 2>/dev/null; xdotool type --delay 80 "$1"; }
shot 1.2 01-typing
shot 5.5 02-typed
( plymouth ask-for-password --prompt="Please unlock disk cryptroot" > /out/answer1 2>&1 ) &
shot 1 03-prompt
keys "secret"
shot 0.5 04-bullets
xdotool key Return
shot 0.6 05-working
( plymouth ask-for-password --prompt="Please unlock disk cryptroot" > /out/answer2 2>&1 ) &
shot 1 06-fail
keys "ab"
shot 0.5 07-retype
xdotool key Return
shot 0.6 08-working
plymouth quit
sleep 0.5
chmod -R a+rw /out
'
ls "$OUT"; cat "$OUT/answer1" "$OUT/answer2"
