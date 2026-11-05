"""Fixed stock APPLICATION restore. --execute performs real device writes.
No COMPLETE; fixed117 pages16..132; boot/settings/info excluded by RAM guard.
Failure after DATA starts a read-only host keepalive; power-loss recovery is not established.
"""
from pathlib import Path
from datetime import datetime, timezone
import sys, json, hashlib, struct, functools, argparse, time
if not __debug__:
    raise SystemExit('Safety assertions required: do not run this tool with Python -O')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from usb_block_reader import BlockReader
from read_boot_metadata import build, LOW, HIGH
from boot_console import hid, open_bootloader

STUB_SHA = 'e4c466571f03c5ece7ae4417c281dd9be3787d659945633acec7cfb92dae3a8c'
RELEASE_SHA = '57332cb094949feeba32c44fa829bb57069eaef61d92bceab161601737af4323'
HOLD_SHA = '1c04bf5c4c9ae72885acfd8a62dc948219bb36c4cbc7a12ea3106367a0ebf871'
BODY_SHA = '7f7f5853e7192c737be85cc00e0b21db56e8a40bd68495900002921ef914762c'
META_SHA = '3bce58cb1e15aa6adfb8120c12b6911466a8d1f611a3efeefcb72c6bd7ca4d49'
ORIGINAL_SHA = '5adca278d90a0672e05dfe5ad47d1635242f9ec0ff78827d83d9f28d6ccd8b49'
HEADER_SHA = '3a555131918325b6d55eef48d7b2299ab872bfa1b6caa4659458db6ced1a2fc5'

def digest(data): return hashlib.sha256(data).hexdigest()

def send(channel, frame):
    for pos in range(0, len(frame), 64):
        if channel.h.write(b'\0' + bytes(frame[pos:pos+64]).ljust(64, b'\0')) != 65:
            raise RuntimeError('Short HID write')

def receive(channel, packet, sequence, length):
    reply = bytes(channel.h.read(65, 10000))
    if len(reply) == 65 and reply[0] == 0: reply = reply[1:]
    assert len(reply) == 64 and reply[:4] == bytes([packet, sequence, 0, 0x73]) and reply[6:8] == bytes.fromhex('0177'), reply.hex()
    assert struct.unpack_from('<H', reply, 4)[0] == length, reply.hex()
    return reply

def metadata(reader):
    result = bytearray()
    for address in range(LOW, HIGH, 56):
        length = min(56, HIGH-address)
        image = build(address, length)
        frame = bytearray(reader.channel.original)
        frame[52:492] = image
        struct.pack_into('<I', frame, 492, functools.reduce(int.__xor__, struct.unpack('<110I', image), 0))
        send(reader.channel, frame)
        result.extend(receive(reader.channel, 1, 0, length)[8:8+length])
    return bytes(result)

def snapshot(reader, path, stage):
    result = bytearray()
    with path.open('wb') as stream:
        for address in range(0, 0x20000, 4096):
            data = reader.read(address, 4096)
            result.extend(data); stream.write(data); stream.flush()
            if address % 0x4000 == 0 or address+4096 == 0x20000:
                print(json.dumps(dict(stage=stage, bytes_read=address+4096, total=0x20000)), flush=True)
    return bytes(result)

def start_frame(channel, image):
    frame = bytearray(channel.original); frame[52:492] = image
    struct.pack_into('<I', frame, 492, functools.reduce(int.__xor__, struct.unpack('<110I', image), 0))
    return frame

def hold_after_error(channel, log, save):
    """Keep servicing the verified RAM-only boot-menu holder; never auto-flash."""
    holder = (ROOT/'stock_restore/hold_stub.bin').read_bytes()
    assert digest(holder) == HOLD_SHA
    attempts = 0
    print('RESTORE ERROR: entering read-only bootloader keepalive; no further programming. Keep power connected.', flush=True)
    while True:
        try:
            if channel.h is None:
                devices = [d for d in hid.enumerate(0x352d, 0x1101) if d['path'] == channel.restore_boot_path]
                if len(devices) != 1: raise RuntimeError('Original bootloader path unavailable; will not open another device')
                channel.h = hid.device(); channel.h.open_path(channel.restore_boot_path)
            send(channel, start_frame(channel, holder))
            reply = receive(channel, 1, 0, 6)
            assert reply[8:14] == bytes.fromhex('fff706f933e0')
            log['error_hold_confirmed'] = True
            log['error_hold_keepalives'] = log.get('error_hold_keepalives', 0)+1
            save()
        except Exception as error:
            log['error_hold_last_error'] = repr(error)
            if channel.h:
                channel.h.close(); channel.h = None
        attempts += 1
        if attempts % 40 == 1:
            print(json.dumps(dict(stage='error_readonly_keepalive', confirmed=log.get('error_hold_confirmed', False), attempts=attempts)), flush=True)
        time.sleep(0.25)

def main(execute):
    body = (ROOT/'stock_flash_preparation/20261103T052626Z/stock_application_pages.bin').read_bytes()
    stub = (ROOT/'stock_restore/bounded_stock_stub_v3.bin').read_bytes()
    release = (ROOT/'stock_restore/release_stub.bin').read_bytes()
    assert digest(body) == BODY_SHA and len(body) == 117*512
    assert digest(stub) == STUB_SHA and len(stub) == 440
    assert digest(release) == RELEASE_SHA and len(release) == 440
    assert digest((ROOT/'stock_restore/hold_stub.bin').read_bytes()) == HOLD_SHA
    validation = json.loads((ROOT/'stock_restore/bounded_stock_stub_v3_validation.json').read_text())
    assert validation['passed'] and validation['sha256'] == STUB_SHA
    accepted_pages = {case['page'] for case in validation['cases'] if case['accepted']}
    assert accepted_pages == set(range(16, 133)) and validation['valid_page_operations'] == 234
    protocol = json.loads((ROOT/'stock_restore/protocol_transition_v3_validation.json').read_text())
    assert protocol['passed_native_protocol_audit'] and protocol['requested_in_place_reader_transition_works'], 'Native last-page readback handoff must be validated'
    assert protocol['stub_sha256'] == STUB_SHA and protocol['body_sha256'] == BODY_SHA
    assert protocol['no_COMPLETE'] and protocol['all_14976_program_words_match_stock']
    release_proof = json.loads((ROOT/'stock_restore/protocol_release_v3_validation.json').read_text())
    assert release_proof['passed_native_protocol_audit'] and release_proof['stub_sha256'] == STUB_SHA
    assert release_proof['body_sha256'] == BODY_SHA and release_proof['no_COMPLETE']
    failure_proof = json.loads((ROOT/'stock_restore/failure_reentry_v3_validation.json').read_text())
    assert failure_proof['passed'] and failure_proof['stub_sha256'] == STUB_SHA
    if not execute:
        print(json.dumps(dict(prepared_only=True, body_sha256=BODY_SHA, stub_sha256=STUB_SHA,
                              application_range='0x2000..0x109ff', pages=117, no_COMPLETE=True), indent=2))
        return
    apps = hid.enumerate(0x3532, 0xa0a3)
    assert len(apps) == 6 and len([d for d in apps if d['usage_page'] == 0xff00 and d.get('serial_number') == 'rankednova']) == 1, 'Require running original application'
    assert not hid.enumerate(0x352d, 0x1101), 'Refuse an already-present bootloader device'
    out = ROOT/'stock_restore'/datetime.now(timezone.utc).strftime('live_%Y%m%dT%H%M%SZ')
    out.mkdir(exist_ok=False)
    log = dict(kind='Actual in-place plaintext stock application restore', body_sha256=BODY_SHA,
               stub_sha256=STUB_SHA, application_start='0x2000', application_end_exclusive='0x10a00',
               initial_application_collections=len(apps), no_COMPLETE=True, pages=[], write_started=False,
               verified=False, persistent_caveat='Vendor mode transitions may append bookkeeping; comparisons are within one boot session')
    reader = BlockReader(); channel = reader.channel
    def save(): (out/'result.json').write_text(json.dumps(log, indent=2), encoding='utf-8')
    try:
        reader.open(); log['version'] = channel.version; save()
        assert not hid.enumerate(0x3532, 0xa0a3) and len(hid.enumerate(0x352d, 0x1101)) == 1, 'Require exclusive application-to-bootloader transition'
        channel.restore_boot_path = hid.enumerate(0x352d, 0x1101)[0]['path']
        assert channel.original[6] == 1 and struct.unpack_from('<I', channel.original, 8)[0] == 0x1cc00
        assert digest(channel.original[:52]) == HEADER_SHA, 'Captured START header changed'
        before = snapshot(reader, out/'before_flash.bin', 'prewrite_backup')
        original = (ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
        assert digest(original) == ORIGINAL_SHA, 'Original backup reference changed'
        assert before[:0x1a000] == original[:0x1a000], 'Current boot/app differs from stock reference'
        assert before[0x2000:0x10a00] == body
        mb = metadata(reader); (out/'before_metadata.bin').write_bytes(mb)
        assert digest(mb) == META_SHA, 'Boot information changed'
        log['before_flash_sha256'] = digest(before); log['before_metadata_sha256'] = digest(mb); save()
        # Captured length/cipher header unchanged. Stop at117 code pages, then
        # use read-only STARTs for readback. Never issue metadata COMPLETE.
        frame = start_frame(channel, stub)
        send(channel, frame); reply = receive(channel, 1, 0, 1)
        assert reply[8] == 4; log['start_reply'] = reply.hex(); save()
        for index in range(117):
            page = body[index*512:(index+1)*512]; sequence = index+1
            frame = bytes([2, sequence, 0, 0x73, 0, 2, 1, 0x77]) + page
            assert 16 <= 16+index <= 132 and len(frame) == 520
            log['write_started'] = True; save()
            send(channel, frame); reply = receive(channel, 2, sequence, 1)
            record = dict(sequence=sequence, page=16+index, cpu_address=hex(0x2000+index*512),
                          sha256=digest(page), native_status=reply[8], reply_hex=reply.hex())
            log['pages'].append(record); save(); assert reply[8] == 4, record
            if sequence == 1 or sequence % 16 == 0 or sequence == 117:
                print(json.dumps(dict(stage='stock_application_restore', pages_acknowledged=sequence, total=117)), flush=True)
        after = snapshot(reader, out/'after_flash.bin', 'readback_verify')
        ma = metadata(reader); (out/'after_metadata.bin').write_bytes(ma)
        log.update(after_flash_sha256=digest(after), after_metadata_sha256=digest(ma),
                   application_readback_matches=after[0x2000:0x10a00] == body,
                   bootloader_unchanged=after[:0x2000] == before[:0x2000],
                   outside_application_unchanged=after[:0x2000]+after[0x10a00:] == before[:0x2000]+before[0x10a00:],
                   hidden_metadata_unchanged=ma == mb, whole_flash_matches_prewrite=after == before)
        save(); assert after == before and ma == mb, 'Readback mismatch: KEEP DEVICE IN BOOTLOADER'
        log['verified'] = True; save()
        send(channel, start_frame(channel, release))
        reply = receive(channel, 1, 0, 1)
        assert reply[8] == 4
        log['verified_release_sent'] = True; save()
    except Exception as error:
        log['error'] = repr(error); save()
        if log['write_started'] and not log['verified']:
            hold_after_error(channel, log, save)
        raise
    finally:
        if channel.h and (not log['write_started'] or log['verified']):
            try:
                # A verified release START is already active; GETV closes it.
                log['cleanup'] = dict(final_state=channel.close()) if log['verified'] else reader.close()
            except Exception as error: log['cleanup_error'] = repr(error)
        elif channel.h:
            channel.h.close(); channel.h = None; log['unverified_session_detached'] = True
        save()
    assert log.get('cleanup', {}).get('final_state', {}).get('application_collections') == 6, 'Original application not confirmed'
    assert log['cleanup']['final_state']['bootloader_interfaces'] == 0, 'Bootloader still present'
    log['passed'] = True; save()
    print(json.dumps(dict(result_file=(out/'result.json').as_posix(), passed=True,
                          pages=len(log['pages']), verified=True, cleanup=log['cleanup']), indent=2), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    main(parser.parse_args().execute)
