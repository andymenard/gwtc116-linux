#!/bin/sh
# Remove everything install.sh added. Run as your normal user.
set -e

systemctl --user disable --now vkbd-follow-tablet-mode.service 2>/dev/null || true
rm -f ~/.local/bin/vkbd-follow-tablet-mode ~/.config/systemd/user/vkbd-follow-tablet-mode.service
systemctl --user daemon-reload

sudo sh -c '
    systemctl disable --now gwtc116-tablet-mode 2>/dev/null || true
    rm -f /usr/local/bin/gwtc116-tablet-mode /etc/systemd/system/gwtc116-tablet-mode.service
    systemctl daemon-reload
    rm -f /etc/udev/rules.d/99-gwtc116-touchscreen.rules /etc/udev/hwdb.d/61-gwtc116-sensor.hwdb
    systemd-hwdb update
    udevadm control --reload
    if [ -f /lib/firmware/silead/mssl1680.fw.bak ]; then
        mv /lib/firmware/silead/mssl1680.fw.bak /lib/firmware/silead/mssl1680.fw
    else
        rm -f /lib/firmware/silead/mssl1680.fw
    fi
'
echo "Removed. Reboot to finish."
