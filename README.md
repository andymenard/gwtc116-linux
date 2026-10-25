# Linux fixes for the Gateway GWTC116-2 (11.6" 2-in-1)

Makes the touchscreen, auto-rotation, and tablet mode work on the Gateway
GWTC116-2 under Linux. Tested on Kubuntu 26.04 (KDE Plasma 6.6, kernel 7.0).

| Problem | Fix |
|---|---|
| Touchscreen (Silead MSSL1680) does nothing | Firmware extracted from the Windows driver |
| Touches land in the wrong place | libinput calibration matrix (9-point calibrated) |
| No tablet mode: keyboard stays active when folded, no auto-rotate | Service that computes the hinge angle from the two accelerometers |
| Auto-rotate turns left when it should turn right | Mount-matrix fix for the display accelerometer |
| On-screen keyboard pops up in laptop mode | User service that enables it only in tablet mode (KDE) |

## Install

```sh
git clone https://github.com/<you>/gwtc116-linux
cd gwtc116-linux
./install.sh
```

Run it as your normal user; it asks for your sudo password once. Reboot if the
touchscreen does not respond right away. `./uninstall.sh` removes everything.

## What each part does

### Touchscreen firmware — `firmware/silead/mssl1680.fw`

The Silead chip has no built-in firmware; the driver uploads it on every boot.
The kernel's `silead` driver already supports the chip but needs a firmware file
made for this exact panel. This one was extracted from the laptop's own Windows
driver (`SileadTouch.sys`) with `tools/extract-silead-fw.py`.

SHA-256: `fb36a08e3c52db26eb7fa952bf52400dacb599973e7394f3ac8baaffac40213e`

To extract it yourself from a copy of the Windows driver
(`C:\Windows\System32\drivers\SileadTouch.sys`):

```sh
python3 tools/extract-silead-fw.py SileadTouch.sys mssl1680.fw
```

> **Note:** the firmware is © Silead and is included only for convenience so
> this hardware can be used with Linux. It is not covered by this repository's
> license. If you are the rights holder and want it removed, please open an issue.

### Touchscreen calibration — `touchscreen/99-gwtc116-touchscreen.rules`

The firmware reports X mirrored and with a different range from the screen.
The udev rule sets `LIBINPUT_CALIBRATION_MATRIX` to correct that.

If touches are slightly off on your unit, open `touchscreen/calibrate9.html` in
Firefox, tap the 9 crosshairs, and press **Save calibration**. Then install the
downloaded rule:

```sh
sudo install -m 644 ~/Downloads/touch-calibration.rules /etc/udev/rules.d/99-gwtc116-touchscreen.rules
```

Reboot to apply it. The page builds on the matrix shipped here (the `CURRENT`
constant in the page). If you run it again after installing your own
calibration, update `CURRENT` to the new matrix first. Open
`calibrate9.html#test` to check accuracy without changing anything.

### Tablet mode — `tablet-mode/`

The laptop has two accelerometers, one in the screen (`KIOX010A`) and one in the
base (`KIOX020A`). Windows compares them to get the hinge angle. Linux has no
equivalent, and the kernel deliberately disables the firmware tablet-mode
switch on these dual-accelerometer machines.

`gwtc116-tablet-mode` (a root systemd service, Python standard library only)
reads both sensors 4 times a second and computes the hinge angle. Past 200°
(tent, stand, or tablet), it:

* reports `SW_TABLET_MODE` through a virtual input switch, so the desktop enters
  tablet mode (auto-rotation, on-screen keyboard; tested with KDE Plasma), and
* inhibits the built-in keyboard and touchpad.

Below 170° it switches back. When the service stops, it always re-enables the
keyboard and touchpad. Notes:

* The base sensor is mounted turned 90° relative to the screen sensor. The
  service corrects for this.
* Folded fully back (360°) and closed (0°) read the same. The service tracks
  the angle continuously and uses the lid switch to tell them apart.
* With the hinge vertical (holding the tablet in portrait), the angle can't be
  measured, so the current mode is kept.

Run `sudo gwtc116-tablet-mode --dry-run -v` to see the live hinge angle, or
watch the service with `journalctl -u gwtc116-tablet-mode -f`.

### Rotation direction — `sensors/61-gwtc116-sensor.hwdb`

The display accelerometer reports X mirrored, so `iio-sensor-proxy` rotates the
wrong way. This hwdb entry sets `ACCEL_MOUNT_MATRIX` for it.

### Virtual keyboard — `virtual-keyboard/`

A user service that listens for KWin's tablet-mode changes and turns the
virtual keyboard on only in tablet mode. It's KDE Plasma (Wayland) only. In
KDE, choose the keyboard under System Settings → Keyboard → Virtual Keyboard
(e.g. Plasma Keyboard).

## License

Scripts and configuration: MIT (see `LICENSE`). The firmware file is not
covered (see the note above).
