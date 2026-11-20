- **Shutting down and restarting in the NIRUX look.** The banner and the line
  at once, then `[ ok ] session closed` and `[ .. ] powering off` (or
  `restarting`) with the blinking cursor. Debian and Arch use Plymouth's own
  plymouth-poweroff and plymouth-reboot units; Void gets
  `/etc/runit/shutdown.d/15-nirusplash.sh`, which starts the splash once the
  services have stopped. `nirusplash doctor` checks it on Void, `remove` takes
  it out.

The NIRUX look for the start of the computer: the GRUB menu with the NIRUX
banner and every kernel, and the disk password asked on the NIRUX boot splash.
