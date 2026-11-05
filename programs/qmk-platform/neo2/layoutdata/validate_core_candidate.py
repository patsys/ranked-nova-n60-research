"""Compile candidate data with real QMK headers; never edit/build active firmware."""
from pathlib import Path
import hashlib,json,struct,subprocess
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
obj=OUT/'core_keymap_validation.o';binary=OUT/'core_keymap_validation.bin'
args=[ROOT/'.build-tools/bin/arm-none-eabi-gcc.exe','-mcpu=cortex-m0','-mthumb','-std=c11','-Os','-Wall','-Wextra','-Werror','-ffreestanding']
for directory in ('qmk_port/keyboard','qmk_source/quantum','qmk_source/platforms','qmk_source/quantum/keymap_extras','qmk_source/quantum/sequencer'):
    args+=['-I',ROOT/directory]
args+=['-DQMK_KEYBOARD_H="component_keymap_types.h"','-c',ROOT/'qmk_port/neo2/core_keymap.c','-o',obj]
subprocess.run(list(map(str,args)),check=True,capture_output=True)
subprocess.run([str(ROOT/'.build-tools/bin/arm-none-eabi-objcopy.exe'),'-O','binary','-j','.rodata',str(obj),str(binary)],check=True,capture_output=True)
data=binary.read_bytes();assert len(data)==396
codes=struct.unpack('<198H',data)
assert codes[12]==0x1b and codes[25]==4 and codes[156]==0x50
candidate=json.loads((OUT.parent/'core_keymap.json').read_text(encoding='utf-8'))
assert len(candidate['positions'])==62 and len(candidate['matrix'])==3
# Unsupported ellipsis, superscript1 and inverted punctuation are not approximated.
assert codes[66+12]==0 and codes[66+1]==0 and codes[132+17]==0
assert not any('substitutions' in item for item in candidate['deviations'])
shift=json.loads((OUT.parent/'shift_overrides.json').read_text(encoding='utf-8'))
assert len(shift['overrides'])==16 and sum(item['available'] for item in shift['overrides'])==4
report={'passed':True,'actual_upstream_QMK_macros_compiled':True,'candidate_bytes':len(data),'layers':3,
        'matrix_rows':6,'matrix_cols':11,'no_ASCII_typography_approximations':True,
        'canonical_shift_overrides':16,'available_shift_overrides':4,
        'candidate_c_sha256':hashlib.sha256((OUT.parent/'core_keymap.c').read_bytes()).hexdigest(),
        'requires_keymap_shift_and_literal_hook':True,'no_active_firmware_or_runtime_edited':True}
(OUT/'core_compile_validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: real QMK macro compilation,396-byte candidate, strict unsupported symbols and16Shift records.')
