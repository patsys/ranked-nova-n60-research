"""Execute recovered USB transmit routine offline; never opens a device."""
import sys, json, struct
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / '.tools'))
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

flash = (ROOT / 'firmware_dump/flash_cpu_pass1.bin').read_bytes()
results = []
for ep in range(6):
    for length in (0, 1, 64):
        uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        uc.mem_map(0, 0x20000); uc.mem_write(0, flash)
        uc.mem_map(0x20000000, 0x10000)
        uc.mem_map(0x40000000, 0x20000)
        uc.mem_map(0xe000e000, 0x2000)
        uc.mem_write(0x20001340 + 4*ep, struct.pack('<I', 1))
        data = bytes((0x80+i)&255 for i in range(length))
        uc.mem_write(0x20002000, data or b'\0')
        uc.reg_write(UC_ARM_REG_SP, 0x2000f000)
        uc.reg_write(UC_ARM_REG_LR, 0x1f001)
        for reg, value in ((UC_ARM_REG_R0, ep), (UC_ARM_REG_R1, 0x20002000), (UC_ARM_REG_R2, length)):
            uc.reg_write(reg, value)
        writes = []; returned = []
        def code(u, addr, size, _):
            if addr == 0x1f000:
                returned.append(True); u.emu_stop()
        def write(u, access, addr, size, value, _):
            if 0x40000000 <= addr < 0x40020000:
                writes.append({'pc': hex(u.reg_read(UC_ARM_REG_PC)), 'address': hex(addr), 'size': size, 'value': value})
        uc.hook_add(UC_HOOK_CODE, code); uc.hook_add(UC_HOOK_MEM_WRITE, write)
        uc.emu_start(0xf119, 0x1f000, count=10000)
        fifo = 0x40017c00 - ep*0x200
        expected = [{'address': hex(fifo+i*4), 'size': 4, 'value': b} for i,b in enumerate(data)]
        expected.append({'address': hex(0x40017ed4+8*ep), 'size': 4, 'value': length})
        observed = [{k:v for k,v in w.items() if k != 'pc'} for w in writes]
        assert observed == expected, (ep, length, observed, expected)
        assert uc.reg_read(UC_ARM_REG_PC) == 0x1f000
        assert uc.mem_read(0x20001340+4*ep,4) == b'\0'*4
        results.append({'endpoint':ep, 'length':length, 'writes':writes, 'passed':True})
out = ROOT / 'firmware_dump/usb_tx_offline_traces.json'
out.write_text(json.dumps({'method':'Unicorn execution of recovered original routine 0xf118; zero-filled MMIO, initialized ready flag; no hardware model or device access', 'cases':results}, indent=2))
print(f'{len(results)} offline TX cases passed; {out}')
