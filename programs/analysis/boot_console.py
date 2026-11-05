"""Read-only bootloader request/reply client; no update operations.

--enter-bootloader sends the previously verified app mode-switch command.
There is deliberately no arbitrary command or firmware-transfer option.
"""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent / '.tools'))
import hid

QUERY = bytes.fromhex('0000000004000001') + b'getv'


def open_bootloader(enter=False):
    devices = hid.enumerate(0x352d, 0x1101)
    if not devices and enter:
        apps = [d for d in hid.enumerate(0x3532, 0xa0a3)
                if d['usage_page'] == 0xff00]
        if len(apps) != 1:
            raise RuntimeError('Expected exactly one application vendor interface')
        app = hid.device()
        try:
            app.open_path(apps[0]['path'])
            if app.write(bytes.fromhex('04a501') + bytes(61)) != 64:
                raise RuntimeError('Short mode-switch write')
        finally:
            app.close()
        for _ in range(40):
            devices = hid.enumerate(0x352d, 0x1101)
            if devices:
                break
            time.sleep(0.1)
    if len(devices) != 1:
        raise RuntimeError('Expected exactly one bootloader interface')
    h = hid.device()
    h.open_path(devices[0]['path'])
    return h


def get_version(h):
    started = time.monotonic()
    count = h.write(b'\0' + QUERY.ljust(64, b'\0'))
    if count != 65:
        raise RuntimeError(f'Short query write: {count}')
    reply = bytes(h.read(65, 2000))
    # hidapi can include a zero report ID on some backends.
    payload = reply[1:] if len(reply) == 65 and reply[0] == 0 else reply
    expected_header = bytes.fromhex('0000000010000001')
    if len(payload) < 24 or payload[:8] != expected_header or payload[8:16] != b'version:':
        raise RuntimeError(f'Unexpected query reply: {reply.hex()}')
    return dict(request_hex=QUERY.hex(), response_hex=reply.hex(),
                round_trip_ms=round((time.monotonic()-started)*1000, 2),
                version_words_hex=[payload[16:20].hex(), payload[20:24].hex()])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enter-bootloader', action='store_true')
    parser.add_argument('--count', type=int, choices=range(1, 11), default=1)
    args = parser.parse_args()
    log = dict(protocol='vendor bootloader getv; not custom stub RPC', exchanges=[])
    device = None
    try:
        device = open_bootloader(args.enter_bootloader)
        for _ in range(args.count):
            exchange = get_version(device)
            log['exchanges'].append(exchange)
            print(json.dumps(exchange), flush=True)
    except Exception as error:
        log['error'] = str(error)
        raise
    finally:
        if device:
            device.close()
        Path('boot_console_live.json').write_text(json.dumps(log, indent=2))
