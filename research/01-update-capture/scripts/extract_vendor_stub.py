"""Recover the observed plaintext stub from the saved USBPcap, offline only."""
from pathlib import Path
import hashlib
import struct


def extract(path):
    blob = Path(path).read_bytes()
    if blob[:4] != bytes.fromhex('d4c3b2a1'):
        raise ValueError('Expected little-endian microsecond PCAP')
    if struct.unpack_from('<I', blob, 20)[0] != 249:
        raise ValueError('Expected USBPcap link type')
    reports = []
    pos = 24
    while pos < len(blob):
        if pos + 16 > len(blob):
            raise ValueError('Truncated packet header')
        size = struct.unpack_from('<I', blob, pos + 8)[0]
        end = pos + 16 + size
        if end > len(blob):
            raise ValueError('Truncated packet')
        packet = blob[pos + 16:end]
        pos = end
        if len(packet) < 27:
            continue
        header_size = struct.unpack_from('<H', packet)[0]
        data_size = struct.unpack_from('<I', packet, 23)[0]
        # Observed outgoing interrupt endpoint, submit side, 64-byte reports.
        if (header_size == 27 and packet[16] == 0 and packet[21] == 4
                and packet[22] == 1 and data_size == 64 and len(packet) == 91):
            reports.append(packet[27:])
    for index, report in enumerate(reports):
        if report[:4] != b'\x01\x00\x00\x73' or report[7] != 0x77:
            continue
        payload_size = struct.unpack_from('<H', report, 4)[0]
        total = payload_size + 8
        frame = b''.join(reports[index:index + (total + 63) // 64])[:total]
        if len(frame) != total or total < 52:
            raise ValueError('Incomplete START frame')
        stub_size = struct.unpack_from('<I', frame, 48)[0]
        if stub_size != 440 or 52 + stub_size > len(frame):
            raise ValueError('Unexpected stub layout')
        return frame, frame[52:52 + stub_size]
    raise ValueError('No matching START frame')


if __name__ == '__main__':
    frame, stub = extract('fw_update.pcap')
    Path('vendor_stub.bin').write_bytes(stub)
    print(f'START: {len(frame)} bytes; stub: {len(stub)} bytes')
    print(f'SHA256: {hashlib.sha256(stub).hexdigest()}')
    print(f'First 16 bytes: {stub[:16].hex()}')
