#!/bin/sh
# Install the Gateway GWTC116-2 fixes. Run as your normal user (not root);
# it asks for sudo for the system-wide parts.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$(id -u)" -eq 0 ]; then
    echo "Run as your normal user: ./install.sh (it uses sudo where needed)"; exit 1
fi
model=$(cat /sys/class/dmi/id/product_name 2>/dev/null)
if [ "$model" != "GWTC116-2" ] && [ "$1" != "--force" ]; then
    echo "This is for the Gateway GWTC116-2, but this machine reports '$model'."
    echo "Use ./install.sh --force to install anyway."; exit 1
fi

echo "== Touchscreen firmware, calibration, accelerometer fix, tablet-mode service"
sudo sh -e -c "
    if [ -f /lib/firmware/silead/mssl1680.fw ] && ! cmp -s '$DIR/firmware/silead/mssl1680.fw' /lib/firmware/silead/mssl1680.fw; then
        cp /lib/firmware/silead/mssl1680.fw /lib/firmware/silead/mssl1680.fw.bak
        echo 'Existing firmware backed up to /lib/firmware/silead/mssl1680.fw.bak'
    fi
    install -D -m 644 '$DIR/firmware/silead/mssl1680.fw' /lib/firmware/silead/mssl1680.fw
    install -m 644 '$DIR/touchscreen/99-gwtc116-touchscreen.rules' /etc/udev/rules.d/
    install -m 644 '$DIR/sensors/61-gwtc116-sensor.hwdb' /etc/udev/hwdb.d/
    systemd-hwdb update
    udevadm control --reload
    install -m 755 '$DIR/tablet-mode/gwtc116-tablet-mode.py' /usr/local/bin/gwtc116-tablet-mode
    install -m 644 '$DIR/tablet-mode/gwtc116-tablet-mode.service' /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable gwtc116-tablet-mode
    systemctl restart gwtc116-tablet-mode
    modprobe -r silead || true
    modprobe silead
    udevadm trigger --action=change --subsystem-match=iio
    systemctl restart iio-sensor-proxy || true
"

echo "== Virtual keyboard only in tablet mode (KDE Plasma)"
install -D -m 755 "$DIR/virtual-keyboard/vkbd-follow-tablet-mode" ~/.local/bin/vkbd-follow-tablet-mode
install -D -m 644 "$DIR/virtual-keyboard/vkbd-follow-tablet-mode.service" ~/.config/systemd/user/vkbd-follow-tablet-mode.service
systemctl --user daemon-reload
systemctl --user enable --now vkbd-follow-tablet-mode.service || \
    echo "(Could not start it now; it will start at your next KDE login.)"

echo
echo "Done. If the touchscreen does not respond yet, reboot."
