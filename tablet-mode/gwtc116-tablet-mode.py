#!/usr/bin/env python3
"""Tablet-mode detection for the Gateway GWTC116-2 (360° hinge, two accelerometers).

Computes the hinge angle from the base and display accelerometers and, when the
screen is folded back past flat:
  * reports SW_TABLET_MODE through a virtual input switch, so KDE enters tablet
    mode (auto-rotation, on-screen keyboard), and
  * inhibits the built-in keyboard and touchpad, as Windows does.

Run as root. --dry-run only prints the angle and the decision.
"""
import fcntl, glob, math, os, signal, struct, sys, time

INTERVAL = 0.25          # seconds between samples
TABLET_ABOVE = 200       # enter tablet mode past this hinge angle (degrees)
LAPTOP_BELOW = 170       # leave tablet mode below this one
MIN_QUALITY = 0.5        # skip samples where the hinge axis is close to vertical
DEBOUNCE = 2             # consecutive samples needed before switching
INHIBIT = ['AT Translated Set 2 keyboard', 'HTIX5288:00 0911:5288 Touchpad']
LID = '/proc/acpi/button/lid/LID0/state'

DRY = '--dry-run' in sys.argv


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ---- sensors ----------------------------------------------------------------

def find_accels():
    found = {}
    for d in glob.glob('/sys/bus/iio/devices/iio:device*'):
        try:
            found[open(d + '/label').read().strip()] = d
        except OSError:
            pass
    return found.get('accel-base'), found.get('accel-display')


def read(d):
    return [int(open(f'{d}/in_accel_{a}_raw').read()) for a in 'xyz']


def measure(base_dev, disp_dev):
    """Return (hinge angle 0..360, quality 0..1)."""
    b, d = read(base_dev), read(disp_dev)
    # The base sensor is mounted turned 90° about Z relative to the display
    # sensor; remap it so both share the hinge as their X axis.
    by, bz = b[0], b[2]
    dy, dz = d[1], d[2]
    g = math.sqrt(sum(v * v for v in b)) or 1
    quality = min(math.hypot(by, bz), math.hypot(dy, dz)) / g
    angle = (math.degrees(math.atan2(dz, dy) - math.atan2(bz, by)) + 180) % 360
    return angle, quality


def lid_open():
    try:
        return 'open' in open(LID).read()
    except OSError:
        return True


# ---- outputs ----------------------------------------------------------------

UI_SET_EVBIT, UI_SET_SWBIT = 0x40045564, 0x4004556d
UI_DEV_SETUP, UI_DEV_CREATE, UI_DEV_DESTROY = 0x405c5503, 0x5501, 0x5502
EV_SYN, EV_SW, SW_TABLET_MODE, BUS_VIRTUAL = 0, 5, 1, 0x06


class TabletSwitch:
    def __init__(self):
        self.fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_SW)
        fcntl.ioctl(self.fd, UI_SET_SWBIT, SW_TABLET_MODE)
        setup = struct.pack('<HHHH80sI', BUS_VIRTUAL, 0, 0, 1, b'GWTC116 tablet mode switch', 0)
        fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
        fcntl.ioctl(self.fd, UI_DEV_CREATE)
        time.sleep(0.5)   # give udev/libinput time to pick up the device

    def _emit(self, typ, code, value):
        t = time.time()
        os.write(self.fd, struct.pack('llHHi', int(t), int(t % 1 * 1e6), typ, code, value))

    def set(self, tablet):
        self._emit(EV_SW, SW_TABLET_MODE, int(tablet))
        self._emit(EV_SYN, 0, 0)

    def close(self):
        fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        os.close(self.fd)


def set_inhibited(on):
    for d in glob.glob('/sys/class/input/input*'):
        try:
            name = open(d + '/name').read().strip()
            if name in INHIBIT:
                open(d + '/inhibited', 'w').write('1' if on else '0')
        except OSError as e:
            log(f'could not {"inhibit" if on else "release"} {d}: {e}')


# ---- main loop --------------------------------------------------------------

def main():
    base_dev, disp_dev = find_accels()
    if not (base_dev and disp_dev):
        sys.exit('accel-base / accel-display not found')

    switch = None if DRY else TabletSwitch()
    tablet = None        # current state
    unwrapped = None     # hinge angle tracked continuously, so 360° ≠ 0°
    pending = 0

    def apply(state):
        nonlocal tablet
        tablet = state
        log(f'{"TABLET" if state else "LAPTOP"} mode (hinge {unwrapped:.0f}°)')
        if not DRY:
            switch.set(state)
            set_inhibited(state)

    def stop(*_):
        raise SystemExit
    signal.signal(signal.SIGTERM, stop)

    try:
        while True:
            angle, quality = measure(base_dev, disp_dev)
            if not lid_open():
                unwrapped = 0.0
                want = False
            elif quality < MIN_QUALITY:
                time.sleep(INTERVAL)
                continue
            else:
                if unwrapped is None:
                    # Starting up: fully folded back and fully closed read the
                    # same; with the lid open it must be folded back.
                    unwrapped = angle + 360 if angle < 30 else angle
                else:
                    unwrapped += (angle - unwrapped + 180) % 360 - 180
                    unwrapped = min(max(unwrapped, -20), 380)
                if unwrapped > TABLET_ABOVE:
                    want = True
                elif unwrapped < LAPTOP_BELOW:
                    want = False
                else:
                    want = bool(tablet)
            if DRY and '-v' in sys.argv:
                log(f'angle {angle:5.1f}  tracked {unwrapped:6.1f}  q {quality:.2f}')
            if tablet is None:
                apply(want)
            elif want != tablet:
                pending += 1
                if pending >= DEBOUNCE:
                    apply(want)
                    pending = 0
            else:
                pending = 0
            time.sleep(INTERVAL)
    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        if not DRY:
            set_inhibited(False)
            switch.close()
        log('stopped; keyboard and touchpad enabled')


if __name__ == '__main__':
    main()
