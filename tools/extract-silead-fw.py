#!/usr/bin/env python3
"""Extract Silead touchscreen firmware from a Windows SileadTouch.sys driver.

The firmware is stored as (register, value) pairs of little-endian u32s, in
pages that each start with a {0xf0, page} marker followed by 32 words at
registers 0x00..0x7c. That is exactly the format the Linux silead driver loads.

Usage: extract-silead-fw.py SileadTouch.sys mssl1680.fw
"""
import struct, sys

PAGE = 33 * 8   # marker + 32 words, 8 bytes each


def is_page(d, i):
    if i + PAGE > len(d):
        return False
    reg, page = struct.unpack_from('<II', d, i)
    if reg != 0xf0 or page > 0xff:
        return False
    return all(struct.unpack_from('<I', d, i + 8 * (k + 1))[0] == 4 * k for k in range(32))


def extract(d):
    best = (0, 0)
    i = 0
    while i < len(d) - PAGE:
        if is_page(d, i):
            j = i
            while is_page(d, j):
                j += PAGE
            if j - i > best[1] - best[0]:
                best = (i, j)
            i = j
        else:
            i += 4
    return d[best[0]:best[1]]


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    fw = extract(open(sys.argv[1], 'rb').read())
    if not fw:
        sys.exit('no firmware found')
    open(sys.argv[2], 'wb').write(fw)
    print(f'{len(fw) // PAGE} pages, {len(fw)} bytes written to {sys.argv[2]}')
