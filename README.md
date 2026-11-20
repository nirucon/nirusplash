# NIRUSPLASH

The NIRUX look for the start of the computer: the GRUB menu and the boot
splash, where an encrypted disk asks for its password in the same style as the
NIRUX lock and login screens.

- **GRUB:** the NIRUX banner, "A MINIMAL X11 DESKTOP" with the cursor, and
  every installed kernel straight in the menu (newest first, each with its
  recovery entry). Arrow keys, Enter, `e` and `c` work as always.
- **Plymouth:** the banner is typed in one `#` at a time, then the line and a
  blinking cursor, as on the lock screen. The disk password is asked at
  `$ unlock disk`, with `[ .. ] unlocking` and `[ fail ] wrong password, try
  again`. Esc shows the start-up messages.
- **Shutting down and restarting:** the banner and the line at once, then
  `[ ok ] session closed` and `[ .. ] powering off` (or `restarting`) with the
  cursor blinking after it. systemd starts it with Plymouth's own
  plymouth-poweroff and plymouth-reboot units; on Void a file in
  `/etc/runit/shutdown.d` does it once the services have stopped.

The pictures are made on the machine for its own screen and the colours of the
NIRUX theme, with nothing but `python3`.

NIRUX installs and updates it (`nirux boot on|off|apply|status|doctor`), and
NIRUBOOT puts it on every new installation. It runs on Debian, Void and Arch
with GRUB.

## Use

```sh
sudo nirusplash install [--background RRGGBB --foreground RRGGBB --muted RRGGBB --focus RRGGBB]
                        [--size WIDTHxHEIGHT] [--timeout SECONDS] [--no-splash]
sudo nirusplash remove      # the plain boot back; "install" turns it on again
nirusplash status [--json]
sudo nirusplash doctor
```

`install` is safe to run again: when nothing changed it does nothing, and the
initramfs is only made again when the splash changed.

## What it changes, and what it never touches

Changed:

- `/boot/grub/themes/nirux` (the theme) and a marked block at the end of
  `/etc/default/grub`: the theme, the font, the screen size, a three-second
  menu, every kernel in the main menu, and `quiet splash` when they are
  missing. `grub.cfg` is then made again.
- `/usr/share/plymouth/themes/nirux` and `/etc/plymouth/plymouthd.conf`; the
  Plymouth package is installed when it is missing.
- The initramfs of the **newest** kernel. Older kernels keep the one they
  had, so the menu always has an entry made without the splash.
- Void: `/etc/runit/core-services/99-nirusplash.sh` stops the splash before
  the login screen starts, `/etc/runit/shutdown.d/15-nirusplash.sh` shows it
  again while the machine stops, and `/etc/dracut.conf.d/90-nirusplash.conf` asks
  dracut for the Plymouth module. Arch: `plymouth` in the mkinitcpio hooks,
  before `encrypt`.

Never touched: the EFI partition, the GRUB binary (no `grub-install`), the
disk encryption, `/etc/crypttab`, the kernel and its command line apart from
`quiet splash`.

How it stays safe:

- every file is made next to its place and checked before it is moved in:
  `grub.cfg` must pass `grub-script-check`, keep its kernel entries and load
  the theme, and the new initramfs must contain the splash;
- on any error everything already changed is put back, newest first;
- originals are kept in `/var/lib/nirusplash/backup`, the log is
  `/var/log/nirusplash.log`;
- there must be room in `/boot` for the new initramfs before it is made.

If the splash ever fails at start-up, choose an older kernel or a recovery
entry in the GRUB menu, or press Esc for the plain prompt; the password is the
same. The keyboard at the prompt is the one the initramfs loads (NIRUBOOT sets
the Swedish one); the splash does not change it.

## Build and test

```sh
tools/build-release.sh                 # dist/nirusplash and dist/SHA256SUMS (Pillow, grub-mkfont, DejaVu)
tests/unit.sh                          # the composer and the installer's text handling
tests/grub-preview.sh build/out/grub 1920 1200 grub.png      # the menu in QEMU (UEFI)
tests/plymouth-preview.sh build/out/plymouth 1920 1200 out/  # the splash and the prompt, in a container
```

The full test installs Debian, Void and Arch with an encrypted disk with
NIRUBOOT, boots them, takes screenshots of the menu and the splash, types the
password on the splash with the Swedish keyboard and logs in
(`NIRUBOOT_TEST_SPLASH=dist/nirusplash tests/vm-test.sh DISTRO yes` in the
NIRUBOOT repository).

## Licence

MIT. The pictures and GRUB fonts are made from DejaVu Sans Mono, see
[FONTS.md](FONTS.md).
