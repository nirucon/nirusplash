- Arch with a Unified Kernel Image (GRUB 2.14+ `uki`): the image itself gets the splash, is backed up and put back on an error, and `quiet splash` go into `/etc/kernel/cmdline` when missing.
- `nirusplash --version` answers without bash (the rest still needs it), so
  NIRUX can check it in minimal containers too.

The NIRUX look for the start of the computer: the GRUB menu with the NIRUX
banner and every kernel, and the disk password asked on the NIRUX boot splash.
