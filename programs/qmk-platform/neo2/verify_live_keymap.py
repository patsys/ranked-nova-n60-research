"""Read-only live verification against the exact Neo2 ELF's compiled keymap."""
from pathlib import Path
import sys, struct, json, hashlib, time, argparse
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from crypto_research.via_state import hid, transfer, get_buffer

def main(rgb=False):
    folder = ROOT / ('qmk_port/build/firmware_via_diagnostic_neo2_rgb' if rgb else 'qmk_port/build/firmware_via_diagnostic_neo2')
    elf = (folder / 'nova_qmk_research.elf').read_bytes()
    expected_hash = '1c63569e9e1dfbf343757fd425856a4891c08a53c4aae54345a465f0cabda88f' if rgb else '8fbed3bc051b69ae5005ae2293566ffaeb2c4b91fbf36e7c53c0539bc700c711'
    assert hashlib.sha256(elf).hexdigest() == expected_hash
    symbols = {p[2]: int(p[0], 16) for line in (folder / 'nova_qmk_research.nm').read_text().splitlines() if len(p := line.split()) == 3}
    address = symbols['keymaps']
    phoff = struct.unpack_from('<I', elf, 28)[0]
    phsize, phnum = struct.unpack_from('<HH', elf, 42)
    expected = None
    for i in range(phnum):
        typ, off, vaddr, _, size, _, _, _ = struct.unpack_from('<8I', elf, phoff+i*phsize)
        if typ == 1 and vaddr <= address and address+396 <= vaddr+size:
            expected = elf[off+address-vaddr:off+address-vaddr+396]
    assert expected is not None
    # ELF stores uint16 keycodes little-endian; VIA serializes them big-endian.
    expected = b''.join(expected[i:i+2][::-1] for i in range(0, 396, 2))
    devices = hid.enumerate(0x3532, 0xa0a3)
    raw = [d for d in devices if d['usage_page'] == 0xff60 and d['usage'] == 0x61]
    assert len(devices) == 2 and len(raw) == 1 and not hid.enumerate(0x352d, 0x1101)
    h = hid.device(); h.open_path(raw[0]['path'])
    try:
        assert transfer(h, [1])[:3] == bytes([1, 0, 13])
        assert transfer(h, [0x11])[1] == 3
        actual = get_buffer(h, 0x12, 396)
        assert actual == expected, 'Live VIA keymap differs from compiled Neo2 default'
        for _ in range(15):
            time.sleep(1)
            assert transfer(h, [1])[:3] == bytes([1, 0, 13])
        assert get_buffer(h, 0x12, 396) == expected
    finally:
        h.close()
    result = dict(passed=True, read_only=True, keymap_bytes=396, layers=3, elf_sha256=expected_hash,
                  protocol=13, keymap_sha256=hashlib.sha256(actual).hexdigest(),
                  soak_seconds=15, flash_writes=False,
                  limitations='Physical typing and Windows character rendering require user validation.')
    (ROOT/('qmk_port/neo2/live_keymap_validation_rgb.json' if rgb else 'qmk_port/neo2/live_keymap_validation.json')).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--rgb',action='store_true');args=parser.parse_args();main(args.rgb)
