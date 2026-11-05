"""Generate three QMK layers from verified original fallback mappings."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
image=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
recovered=json.loads((ROOT/'qmk_port/scan/function_layers.json').read_text())
blocks=[];evidence=[]
for original_layer,qmk_layer in [(0,0),(1,2),(2,1)]:
 layer=recovered['layers'][original_layer]
 entries={(e['bank'],e['channel']):e for e in layer['entries']};rows=[]
 for bank in range(6):
  codes=[]
  for channel in range(11):
   e=entries[bank,channel];location=int(layer['table_address'],16)+e['original_key_id']*2
   assert image[location:location+2]==bytes([e['first_byte'],e['second_byte']])
   code='KC_NO'
   if e['kind']=='momentary_layer1':code='MO(2)'
   elif e['kind']=='momentary_layer2':code='MO(1)'
   elif e['kind']=='basic_hid_usage' and e['first_byte']:
    usage=e['first_byte'];assert 4<=usage<=0xa4 or 0xe0<=usage<=0xe7
    code=f'0x{usage:04x}'
   codes.append(code)
   evidence.append(dict(**e,original_layer=original_layer,qmk_layer=qmk_layer,qmk_code=code,unresolved=e['kind']=='vendor_action'))
  rows.append('        {'+', '.join(codes)+'},')
 blocks.append(f'    [{qmk_layer}] = {{\n'+'\n'.join(rows)+'\n    },')
text='''/* Generated from original fallback tables f6a2/f79e/f89a.
 * Original FF/FE momentary selectors map to MO(2)/MO(1), preserving FF priority.
 * Unsupported vendor actions are KC_NO. User mutable remaps are not imported.
 */
#include QMK_KEYBOARD_H
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
'''+ '\n'.join(blocks)+'\n};\n'
out=ROOT/'qmk_port/keyboard/keymaps/default';out.mkdir(parents=True,exist_ok=True)
(out/'keymap.c').write_text(text,encoding='utf-8')
(ROOT/'qmk_port/keyboard/keymap_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
assert sum(e['unresolved'] for e in evidence if e['original_layer']==0)==0
print('Generated3 layers: base60 HID usages+2 function selectors;15 alternate vendor actions remain KC_NO')
