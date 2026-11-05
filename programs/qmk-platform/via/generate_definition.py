"""Build VIA's diagnostic matrix layout from recovered sample geometry."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2]
geometry=json.loads((ROOT/'firmware_dump/key_scan_tables.json').read_text())
entries=json.loads((ROOT/'qmk_port/scan/function_layers.json').read_text())['layers'][0]['entries']
labels={0x29:'Esc',0x2a:'Backspace',0x2b:'Tab',0x2c:'Space',0x2d:'Minus',0x2e:'Equal',0x2f:'Left bracket',0x30:'Right bracket',0x32:'Non-US hash',0x33:'Semicolon',0x34:'Quote',0x36:'Comma',0x37:'Dot',0x38:'Slash',0x39:'Caps Lock',0x64:'Non-US backslash',0xe0:'Left Ctrl',0xe1:'Left Shift',0xe2:'Left Alt',0xe3:'Left GUI',0xe4:'Right Ctrl',0xe5:'Right Shift',0xe6:'Right Alt',0xff:'Fn1',0xfe:'Fn2',0x28:'Enter'}
for i in range(26):labels[4+i]=chr(ord('A')+i)
for i in range(10):labels[0x1e+i]=str((i+1)%10)
lookup={(e['bank'],e['channel']):e for e in entries}
rows=[];coordinates=[]
for bank in range(6):
    row=[{'a':0}] if bank==0 else []
    gap=0
    for channel in range(11):
        e=lookup[bank,channel]
        if e['kind']=='absent':gap+=1;continue
        if gap:row.append({'x':gap});gap=0
        label=labels.get(e['first_byte'],f"HID {e['first_byte']:02X}")
        # KLE top-left legend is VIA's matrix coordinate. Center legend is only
        # a human-readable diagnostic label; no bottom-right layout-option legend.
        row.append(f'{bank},{channel}\n\n\n\n{label}')
        coordinates.append([bank,channel])
    rows.append(row)
definition={'name':'Ranked Nova N60 Research - bank/channel diagnostic',
            'vendorId':'0x3532','productId':'0xA0A3','matrix':{'rows':6,'cols':11},
            'menus':[],'layouts':{'keymap':rows}}
dest=Path(__file__).with_name('nova_research.json')
dest.write_text(json.dumps(definition,indent=2)+'\n')
expected=[[b,c] for b in range(6) for c in range(11) if geometry['logical_key_ids_by_channel_then_bank'][c][b]!=1]
assert coordinates==expected and len(coordinates)==62 and len(set(map(tuple,coordinates)))==62
metadata={'definition':dest.name,'keys':62,'coordinates_match_recovered_geometry':True,
          'usb_raw_usage_page':'0xFF60','usb_raw_usage_id':'0x61',
          'layout_is_physical_iso':False,'physical_layout':'Diagnostic rows are acquisition bank IDs; columns are acquisition channel IDs.',
          'specification':'https://www.caniusevia.com/docs/specification/',
          'raw_usage_note':'Raw usage selectors belong to USB HID descriptors/client discovery; undocumented JSON properties are deliberately not invented.'}
Path(__file__).with_name('definition_validation.json').write_text(json.dumps(metadata,indent=2)+'\n')
print('PASS: diagnostic VIA definition contains all 62 recovered positions exactly once.')
