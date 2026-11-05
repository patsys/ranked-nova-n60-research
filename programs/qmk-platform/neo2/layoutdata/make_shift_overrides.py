"""Exact supported Neo Shift targets; unsupported symbols are explicit KC_NO."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent;OUT=HERE.parent
canonical=json.loads((HERE/'canonical_neo2.json').read_text(encoding='utf-8'))
candidate=json.loads((OUT/'core_keymap.json').read_text(encoding='utf-8'))
availability=json.loads((HERE/'german_host_availability.json').read_text(encoding='utf-8'))
aliases={record['unicode']:record['qmk_german_alias'] for record in availability['unicode_symbols'] if record['availability']=='direct_chord'}
positions={(x['bank'],x['channel']):x for x in candidate['positions']};overrides=[]
for physical in canonical['physical_board_positions']:
    if 'levels' not in physical:continue
    original=physical['levels']['1'];shifted=physical['levels']['2']
    if original['kind']=='action':continue # Native Shift+Tab/Return preserved.
    if original['kind']=='unicode' and shifted['kind']=='unicode':
        char,target=original['unicode'],shifted['unicode']
        if char==' ' or (char.isalpha() and target==char.upper()):continue
    base_alias=positions[physical['bank'],physical['channel']]['core_outputs'][0]
    target_alias=aliases.get(shifted.get('unicode')) if shifted['kind']=='unicode' else None
    overrides.append({'base_alias':base_alias,'shift_target_alias':target_alias or 'KC_NO',
                      'canonical_shift':shifted,'bank':physical['bank'],'channel':physical['channel'],
                      'physical_hid':physical['physical_hid'],'available':bool(target_alias)})
assert len(overrides)==16 and sum(item['available'] for item in overrides)==4
assert {x['base_alias']:x['shift_target_alias'] for x in overrides if x['available']}=={
    'DE_1':'DE_DEG','DE_2':'DE_SECT','DE_6':'DE_DLR','DE_7':'DE_EURO'}
data={'scope':'Neo base layer0 only; existing layers1Mod3/2Mod4 do not use these Shift overrides',
      'clear_physical_shift_during_override':True,'restore_previous_modifiers_after_tap':True,
      'unavailable_is_consumed_not_fallback':True,'overrides':overrides,
      'literal_mod3_actions':[
          {'layer':1,'keycode_alias':'DE_CIRC','canonical_unicode':'^','tap_sequence':['DE_CIRC','KC_SPC']},
          {'layer':1,'keycode_alias':'DE_GRV','canonical_unicode':'`','tap_sequence':['DE_GRV','KC_SPC']}],
      'release_handling':'Consume releases corresponding to handled presses even if Shift/layer state changed in between; do not leak a base key event.',
      'higher_layers':'Greek/math are not implemented in this three-layer core profile.'}
(OUT/'shift_overrides.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Generated16 exact Shift overrides:4supported German chords,12explicit KC_NO;2Mod3 literal dead-key actions.')
