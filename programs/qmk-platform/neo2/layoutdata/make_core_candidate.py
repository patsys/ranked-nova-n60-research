"""Three-layer Neo2-core candidate for a standard German Windows host.
Does not edit the active default keymap or firmware/build/runtime files.
"""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'qmk_port/neo2'
entries=json.loads((ROOT/'qmk_port/scan/function_layers.json').read_text())['layers'][0]['entries']
base={0x29:'KC_ESC',0x2a:'KC_BSPC',0x2b:'KC_TAB',0x28:'KC_ENT',0x2c:'KC_SPC',
      0xe0:'KC_LCTL',0xe1:'KC_LSFT',0xe2:'KC_LALT',0xe3:'KC_LGUI',0xe4:'KC_RCTL',0xe5:'KC_RSFT',
      0xe6:'MO(2)',0x39:'MO(1)',0x32:'MO(1)',0x64:'MO(2)',0xff:'MO(2)',0xfe:'MO(1)'}
for i in range(10):base[0x1e+i]='DE_'+str((i+1)%10)
base.update({0x2d:'DE_MINS',0x2e:'DE_GRV'})
physical_rows=[([0x14,0x1a,8,0x15,0x17,0x1c,0x18,0x0c,0x12,0x13,0x2f,0x30],
                ['DE_X','DE_V','DE_L','DE_C','DE_W','DE_K','DE_H','DE_G','DE_F','DE_Q','DE_SS','DE_ACUT']),
               ([4,0x16,7,9,0x0a,0x0b,0x0d,0x0e,0x0f,0x33,0x34],
                ['DE_U','DE_I','DE_A','DE_E','DE_O','DE_S','DE_N','DE_R','DE_T','DE_D','DE_Y']),
               ([0x1d,0x1b,6,0x19,5,0x11,0x10,0x36,0x37,0x38],
                ['DE_UDIA','DE_ODIA','DE_ADIA','DE_P','DE_Z','DE_B','DE_M','DE_COMM','DE_DOT','DE_J'])]
for keys,outputs in physical_rows:base.update(zip(keys,outputs))
mod3={}
for keys,outputs in [(physical_rows[0][0],['KC_NO','DE_UNDS','DE_LBRC','DE_RBRC','DE_CIRC','DE_EXLM','DE_LABK','DE_RABK','DE_EQL','DE_AMPR','KC_NO','KC_NO']),
                     (physical_rows[1][0],['DE_BSLS','DE_SLSH','DE_LCBR','DE_RCBR','DE_ASTR','DE_QUES','DE_LPRN','DE_RPRN','DE_MINS','DE_COLN','DE_AT']),
                     (physical_rows[2][0],['DE_HASH','DE_DLR','DE_PIPE','DE_TILD','DE_GRV','DE_PLUS','DE_PERC','DE_DQUO','DE_QUOT','DE_SCLN'])]:mod3.update(zip(keys,outputs))
mod3.update(zip(range(0x1e,0x28),['KC_NO','DE_SUP2','DE_SUP3','KC_NO','KC_NO','KC_NO','KC_NO','KC_NO','KC_NO','KC_NO']))
mod3.update({0x2d:'KC_NO',0x2e:'KC_NO'})
mod4={}
for keys,outputs in [(physical_rows[0][0],['KC_PGUP','KC_BSPC','KC_UP','KC_DEL','KC_PGDN','KC_NO','DE_7','DE_8','DE_9','DE_PLUS','KC_NO','KC_NO']),
                     (physical_rows[1][0],['KC_HOME','KC_LEFT','KC_DOWN','KC_RGHT','KC_END','KC_NO','DE_4','DE_5','DE_6','DE_COMM','DE_DOT']),
                     (physical_rows[2][0],['KC_ESC','KC_TAB','KC_INS','KC_ENT','LCTL(DE_Z)','DE_COLN','DE_1','DE_2','DE_3','DE_SCLN'])]:mod4.update(zip(keys,outputs))
for i,hid in enumerate(range(0x1e,0x28),1):mod4[hid]=f'KC_F{i}'
mod4.update({0x2d:'KC_F11',0x2e:'KC_F12'})
layers=[[['KC_NO']*11 for _ in range(6)] for _ in range(3)];records=[]
for entry in entries:
    bank,channel=entry['bank'],entry['channel'];hid=entry['first_byte']
    if entry['kind']=='absent':continue
    outputs=[base[hid],mod3.get(hid,base[hid]),mod4.get(hid,base[hid])]
    for layer,value in enumerate(outputs):layers[layer][bank][channel]=value
    records.append({'bank':bank,'channel':channel,'original_logical_id':entry['original_key_id'],
                    'physical_original_hid':hex(hid),'core_outputs':outputs})
deviations=[
 {'feature':'Shift typography','canonical':'Neo shifted number/punctuation row includes ° § ℓ » « $ € „ “ ” — ẞ – •',
  'core':'Combine with shift_overrides.json hook: exact German chords for ° § $ €, otherwise explicitly unavailable KC_NO. This is not complete Neo2.'},
 {'feature':'Mod3 unavailable typography','unavailable':['¹','›','‹','¢','¥','‚','‘','’','…','ſ'],
  'core':'KC_NO; no misleading ASCII substitutions.'},
 {'feature':'Dead accents','canonical':'Literal Mod3 ^ and `; dead ring/stroke/doubleacute accents',
  'core':'Combine with keymap hook for Mod3 literal ^/` (dead key followed by Space). Base accents remain dead. Unsupported ring/stroke/doubleacute are KC_NO.'},
 {'feature':'Mod4 top number row','canonical':'ª º № blank · £ ¤ Tab / * - dead diaeresis',
  'core':'F1–F12 to preserve function-key access on the 60% board.'},
 {'feature':'Mod4 unavailable punctuation','unavailable':['¡','¿','−'],'core':'KC_NO, not ASCII approximations.'},
 {'feature':'Control keys','core':'Esc, Tab, Space, Enter, Backspace, Shift, Ctrl, GUI and left Alt preserved. Mod4 Space stays Space instead of canonical keypad0.'},
 {'feature':'Keypad/navigation','core':'Navigation preserved; numpad area emits ordinary German digits/punctuation (NumLock independent). Undo is Ctrl+German Z.'},
 {'feature':'Modifiers','core':'Caps and # are Mod3(MO1); ISO<> and right Alt are Mod4(MO2). Existing Fn2/Fn1 retain MO1/MO2. No Mod3+Shift Greek or Mod3+Mod4 math layer.'}]
data={'profile':'Neo2 core, standard German Windows host, three existing layers',
      'canonical_commit':'cf36e07ce5ff22c51149c3ad933c71fcd770f613',
      'canonical_url':'https://git.neo-layout.org/neo/neo-layout/src/commit/cf36e07ce5ff22c51149c3ad933c71fcd770f613/A-REFERENZ-A/neo20.txt',
      'host_layout':'German QWERTZ; no Neo OS driver and no Unicode helper',
      'layers':{'0':'Neo core letters','1':'Mod3 core symbols','2':'Mod4 navigation + F-row compatibility'},
      'matrix':layers,'positions':records,'deviations':deviations,'physical_keys':len(records),
      'requires_shift_and_literal_dead_key_hook':True}
(OUT/'core_keymap.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['/* Neo2 CORE candidate for a standard German host; NOT complete six-layer Neo2.',
       ' * Requires the Shift/literal-dead-key hook described by shift_overrides.json.',
       ' * See core_keymap.json for explicit unavailable typography/F-row deviations.',
       ' * Canonical Neo reference: commit cf36e07ce5ff22c51149c3ad933c71fcd770f613.',
       ' */','#include QMK_KEYBOARD_H','#include "keymap_german.h"',
       'const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {']
for index,layer in enumerate(layers):
    lines.append(f'    [{index}] = {{')
    for row in layer:lines.append('        {'+', '.join(row)+'},')
    lines.append('    },')
lines.append('};')
(OUT/'core_keymap.c').write_text('\n'.join(lines)+'\n',encoding='utf-8')
assert len(records)==62 and len({(x['bank'],x['channel']) for x in records})==62
assert layers[0][1][1]=='DE_X' and layers[0][2][1]=='DE_U' and layers[1][2][3]=='DE_LCBR' and layers[2][2][2]=='KC_LEFT'
print('Generated candidate only:62 physical keys,3x6x11 matrix; active default keymap untouched.')
if __name__=='__main__':pass
