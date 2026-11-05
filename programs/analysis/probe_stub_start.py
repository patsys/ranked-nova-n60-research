"""One authorized START-only probe. Never sends firmware DATA or COMPLETE."""
from pathlib import Path
import struct
import sys
import json
import hashlib
import argparse
import time
sys.path.insert(0, str(Path(__file__).resolve().parent / '.tools'))
import hid
from extract_vendor_stub import extract

parser = argparse.ArgumentParser()
parser.add_argument('--stateless', action='store_true')
parser.add_argument('--enter-bootloader', action='store_true')
args = parser.parse_args()
frame, old = extract('fw_update.pcap')
frame = bytearray(frame)
stub = Path('readonly_stub/stateless.bin' if args.stateless else 'readonly_stub/diagnostic.bin').read_bytes()
assert len(stub) == len(old) == 440
expected = ('dd26bd7751addc883a196b2a16b5893f0c3fe3e8a5ee3d4cacee18cb4fda8ee5'
            if args.stateless else
            '7bf78ed9a7c88d9e862532c2dd38466b723600dc9417d54cd75f64def4ff5bc8')
assert hashlib.sha256(stub).hexdigest() == expected
assert len(frame) == 496 and frame[0] == 1
assert struct.unpack_from('<I', frame, 492)[0] == __import__('functools').reduce(
    int.__xor__, struct.unpack('<110I', old), 0), 'Vendor checksum mismatch'
frame[52:492] = stub
checksum = __import__('functools').reduce(int.__xor__, struct.unpack('<110I', stub), 0)
struct.pack_into('<I', frame, 492, checksum)
devices = hid.enumerate(0x352d, 0x1101)
if not devices and args.enter_bootloader:
    apps = [d for d in hid.enumerate(0x3532, 0xa0a3) if d['usage_page'] == 0xff00]
    assert len(apps) == 1
    app = hid.device()
    try:
        app.open_path(apps[0]['path'])
        assert app.write(bytes.fromhex('04a501') + bytes(61)) == 64
    finally:
        app.close()
    for _ in range(40):
        devices = hid.enumerate(0x352d, 0x1101)
        if devices:
            break
        time.sleep(0.1)
assert len(devices) == 1, 'Expected one bootloader device'
h = hid.device()
record = dict(operation='START only, diagnostic no-write probe',
              variant='stateless' if args.stateless else 'diagnostic',
              stub_sha256=hashlib.sha256(stub).hexdigest(),
              stub_xor32=hex(checksum), writes=[], replies=[])
try:
    h.open_path(devices[0]['path'])
    query = bytes.fromhex('0000000004000001') + b'getv'
    assert h.write(b'\0' + query.ljust(64, b'\0')) == 65
    version = bytes(h.read(65, 2000))
    record['pre_start_getv'] = version.hex()
    assert b'version:\xa1\x05\x00\x00' in version, 'Unexpected bootloader'
    # Drain pending input without issuing commands.
    for _ in range(10):
        if not h.read(65, 20):
            break
    else:
        raise RuntimeError('Input did not drain; stopping')
    for offset in range(0, len(frame), 64):
        chunk = bytes(frame[offset:offset+64]).ljust(64, b'\0')
        count = h.write(b'\0' + chunk)
        record['writes'].append(count)
        if count != 65:
            raise RuntimeError('Short HID write; stopping without retry')
    for _ in range(3):
        reply = bytes(h.read(65, 1000))
        if reply:
            record['replies'].append(reply.hex())
finally:
    h.close()
    Path('stateless_start_live.json' if args.stateless else 'stub_start_live.json').write_text(json.dumps(record, indent=2))
print(json.dumps(record, indent=2))
