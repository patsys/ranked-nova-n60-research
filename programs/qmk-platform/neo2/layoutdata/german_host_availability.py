"""Audit canonical levels1..4 against the deliberately limited German HID chord set."""
from pathlib import Path
import json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
canonical=json.loads((HERE/'canonical_neo2.json').read_text(encoding='utf-8'))
chords={chr(97+i):'DE_'+chr(65+i) for i in range(26)}
chords.update({chr(65+i):'S(DE_'+chr(65+i)+')' for i in range(26)})
chords.update({str(i):'DE_'+str(i) for i in range(10)})
chords.update(dict(zip(' !"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~',
    ['KC_SPC','DE_EXLM','DE_DQUO','DE_HASH','DE_DLR','DE_PERC','DE_AMPR','DE_QUOT',
     'DE_LPRN','DE_RPRN','DE_ASTR','DE_PLUS','DE_COMM','DE_MINS','DE_DOT','DE_SLSH',
     'DE_COLN','DE_SCLN','DE_LABK','DE_EQL','DE_RABK','DE_QUES','DE_AT','DE_LBRC','DE_BSLS',
     'DE_RBRC','DE_CIRC','DE_UNDS','DE_GRV','DE_LCBR','DE_PIPE','DE_RCBR','DE_TILD'])))
for char,alias in {'ü':'DE_UDIA','ö':'DE_ODIA','ä':'DE_ADIA','ß':'DE_SS','°':'DE_DEG','§':'DE_SECT',
                   '²':'DE_SUP2','³':'DE_SUP3','€':'DE_EURO','µ':'DE_MICR','´':'DE_ACUT'}.items():chords[char]=alias
for char in 'üöä':chords[char.upper()]='S('+chords[char]+')'
symbols={}
for key in canonical['canonical_keys'].values():
    for layer in ('1','2','3','4'):
        symbol=key['levels'][layer]
        if symbol['kind']=='unicode':symbols.setdefault(symbol['unicode'],set()).add(int(layer))
records=[]
for char,layers in sorted(symbols.items(),key=lambda item:ord(item[0])):
    alias=chords.get(char)
    records.append({'unicode':char,'codepoint':f'U+{ord(char):04X}','canonical_layers':sorted(layers),
                    'availability':'dead_key_then_space' if alias and char in '^`´' else 'direct_chord' if alias else 'not_in_audited_chord_set',
                    'qmk_german_alias':alias,'needs_literal_followup_space':bool(alias and char in '^`´')})
assert all(chords[c] for c in '!@#$%&*()[]{}\\|~')
assert not chords.get('ℓ') and not chords.get('¹') and not chords.get('»')
data={'host':'Standard German Windows/QWERTZ, QMK DE_* aliases; no Neo driver/helper',
      'scope':'Direct HID chords audited from QMK keymap_german.h. Not a claim that Windows cannot enter other Unicode via numeric input, Compose or application-specific methods.',
      'unicode_symbols':records,'dead_key_warning':'Core candidate intentionally leaves ^ and ` as German dead keys; no extra runtime macro silently emits Space.',
      'selected_shift_policy':'Use exact supported Neo Shift targets ° § $ € through shift_overrides.json; consume unsupported typography as KC_NO. No silent German-row or ASCII fallback.',
      'source':{'path':'qmk_source/quantum/keymap_extras/keymap_german.h','sha256':hashlib.sha256((ROOT/'qmk_source/quantum/keymap_extras/keymap_german.h').read_bytes()).hexdigest(),
                'sendstring_dead_table_path':'qmk_source/quantum/keymap_extras/sendstring_german.h'}}
(HERE/'german_host_availability.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Wrote direct German-HID availability audit for',len(records),'canonical core Unicode symbols.')
