"""Bounded live test: own no-store stub + up to two synthetic DATA packets.

Never sends vendor code, real firmware, or COMPLETE. ROM behavior is inferred,
not independently proved; a reply alone does not establish stub execution.
"""
from pathlib import Path
import struct
import hashlib
import json
import functools
import time
import sys
from boot_console import open_bootloader, get_version
from extract_vendor_stub import extract

timed = '--timed' in sys.argv
log = dict(operation='no-store timing test' if timed else 'no-store stub challenge test', exchanges=[])
device = None


def exchange(frame, label):
    started = time.perf_counter_ns()
    record = dict(label=label, request_hex=frame.hex(), writes=[], replies=[])
    log['exchanges'].append(record)
    for offset in range(0, len(frame), 64):
        report = b'\0' + frame[offset:offset+64].ljust(64,b'\0')
        n = device.write(report)
        record['writes'].append(n)
        if n != 65:
            raise RuntimeError('Short write; no retry')
    reply = bytes(device.read(65,2000))
    record['replies'].append(reply.hex())
    if len(reply) == 65 and reply[0] == 0:
        reply = reply[1:]
    if len(reply) != 64 or reply[:4] != frame[:4] or reply[4:8] != bytes.fromhex('01000177'):
        raise RuntimeError(f'Unexpected reply; stopping: {reply.hex()}')
    record['response_byte'] = reply[8]
    record['round_trip_ms'] = round((time.perf_counter_ns()-started)/1000000,3)
    print(json.dumps(dict(label=label,response_hex=reply.hex(),round_trip_ms=record['round_trip_ms'])),flush=True)
    return reply[8]


try:
    original, old = extract('fw_update.pcap')
    own = Path('readonly_stub/timing.bin' if timed else 'readonly_stub/echo.bin').read_bytes()
    assert len(own) == 440
    expected = ('9801c5c141c641337588beb70186f4d8ec415eb5e547a4e657a4099cf385a0f6' if timed
                else '2132c2a2c7d9fa30a26353d6b2712863c17cb0eb95ee86ad11192324671b6618')
    assert hashlib.sha256(own).hexdigest() == expected
    frame = bytearray(original)
    assert len(frame) == 496 and frame[0] == 1
    assert struct.unpack_from('<I',frame,492)[0] == functools.reduce(int.__xor__,struct.unpack('<110I',old),0)
    frame[52:492] = own
    struct.pack_into('<I',frame,492,functools.reduce(int.__xor__,struct.unpack('<110I',own),0))
    log['stub_sha256'] = hashlib.sha256(own).hexdigest()
    device = open_bootloader(enter=True)
    log['getv'] = get_version(device)
    if exchange(bytes(frame),'START own echo stub') != 4:
        raise RuntimeError('START not acknowledged; stopping')
    for seq, challenge in [(1,0),(2,1)]:
        # Exact observed DATA framing, followed by synthetic zero RAM input.
        # No actual encrypted firmware bytes are transmitted.
        payload = bytes([challenge]) + bytes(511)
        data = bytes([2,seq,0,0x73,0,2,1,0x77]) + payload
        result = exchange(data, f'DATA synthetic challenge {challenge}')
        if result != 4:
            log['stopped_reason'] = 'Non-success response; no further packets sent'
            break
except Exception as error:
    log['error'] = str(error)
    raise
finally:
    if device:
        device.close()
    Path('timing_probe_live.json' if timed else 'echo_probe_live.json').write_text(json.dumps(log,indent=2))
