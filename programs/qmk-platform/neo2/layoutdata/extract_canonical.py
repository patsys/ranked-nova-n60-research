"""Extract canonical Neo2 data, cross-check all46 key cells against six reference diagrams."""
from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];UP=HERE/'upstream'
manifest=json.loads((UP/'sources.json').read_text())
def read(name):return (UP/name.replace('/','__')).read_text(encoding='utf-8')
xmod=read('linux/xmodmap/neo_de.xmodmap');reference=read('A-REFERENZ-A/neo20.txt')
header=read('grafik/_not_working/xmodmap2tastenaufkleber/keysymdef.h')
definitions={};numeric={}
for line in header.splitlines():
    found=re.match(r'#define\s+XK_(\w+)\s+0x([0-9a-fA-F]+)',line)
    if found:
        name,code=found.group(1),int(found.group(2),16);definitions[name]=code
        unicode=re.search(r'U\+([0-9a-fA-F]{4,6})',line)
        if unicode:numeric[code]=chr(int(unicode.group(1),16))
chars={name:numeric[code] for name,code in definitions.items() if code in numeric}
for line in read('windows/kbdneo2/source/keysym4utf16.h').splitlines():
    found=re.match(r'#define\s+(\w+)\s+0x([0-9a-fA-F]+)',line)
    if found:chars.setdefault(found.group(1),chr(int(found.group(2),16)))
dead={'dead_circumflex':'ˆ','dead_caron':'ˇ','dead_abovedot':'˙','dead_belowdot':'.','dead_grave':'`','dead_cedilla':'¸',
      'dead_abovering':'˚','dead_dasia':'῾','dead_diaeresis':'¨','dead_macron':'¯','dead_acute':'´',
      'dead_tilde':'˜','dead_stroke':'/','dead_psili':'᾿','dead_doubleacute':'˝','dead_breve':'˘'}
action_display={'Tab':'⇥','ISO_Left_Tab':'⇤','Multi_key':'♫','ISO_Level3_Lock':'4Lk','Prior':'⇞','Next':'⇟',
                'BackSpace':'⌫','Delete':'⌦','Up':'⇡','Down':'⇣','Left':'⇠','Right':'⇢','Home':'⇱','End':'⇲',
                'Escape':'⌧','Insert':'⎀','Return':'⏎','KP_Enter':'⏎','Undo':'↶','Redo':'↷',
                'KP_Add':'+','KP_Separator':',','KP_Decimal':'.','KP_Divide':'/','KP_Multiply':'*','KP_Subtract':'-'}
def symbol(name):
    if name=='NoSymbol':return {'keysym':name,'kind':'unassigned','display':''}
    if name in dead:return {'keysym':name,'kind':'dead_key','display':dead[name]}
    if name.startswith('KP_') and name[3:].isdigit():return {'keysym':name,'kind':'keypad_digit','display':name[3:],'digit':int(name[3:])}
    if name in action_display:return {'keysym':name,'kind':'action','display':action_display[name]}
    if len(name)==1:char=name
    elif re.fullmatch('U[0-9A-Fa-f]{4,6}',name):char=chr(int(name[1:],16))
    else:char=chars.get(name)
    if char is None:return {'keysym':name,'kind':'unresolved','display':name}
    return {'keysym':name,'kind':'unicode','display':{'\u00ad':'╌','\u00a0':'⍽','\u202f':'¦'}.get(char,char),
            'unicode':char,'codepoint':f'U+{ord(char):04X}'}
keycodes={}
for line in xmod.splitlines():
    match=re.match(r'keycode\s+(\d+)\s*=\s*([^!]*)',line)
    if match:keycodes[int(match.group(1))]=match.group(2).split()
order=[0,1,2,4,3,6] # Source explicitly declares1,2,3,5,4,4+Shift,6,7.
canonical={}
text_keys=[49,*range(10,22),*range(24,36),*range(38,49),*range(52,62)]
for code in text_keys+[23,36,65]:
    tokens=keycodes[code]+['NoSymbol']*8
    canonical[str(code)]={'xmodmap_keycode':code,'levels':{str(layer+1):symbol(tokens[index]) for layer,index in enumerate(order)}}
checks=[]
headings=['Erste','Zweite','Dritte','Vierte','Fünfte','Sechste']
for layer,heading in enumerate(headings,1):
    block=reference.split(f'=== {heading} Ebene – Miniatur ===',1)[1].split('===',1)[0]
    rows=[line.split('│')[1:-1] for line in block.splitlines() if line.startswith('│')]
    groups=[(rows[0][:13],[49,*range(10,22)]),(rows[1][1:13],list(range(24,36))),
            (rows[2][1:12],list(range(38,49))),(rows[3][2:12],list(range(52,62)))]
    for cells,codes in groups:
        for glyph,code in zip(cells,codes):
            expected=glyph.strip();actual=canonical[str(code)]['levels'][str(layer)]['display']
            assert actual==expected,(layer,code,actual,expected)
            checks.append({'layer':layer,'xmodmap_keycode':code,'display':actual})
assert len(checks)==276
assert not [s for key in canonical.values() for s in key['levels'].values() if s['kind']=='unresolved']
hid_to_x={0x2d:20,0x2e:21,0x2f:34,0x30:35,0x2b:23,0x28:36,0x2c:65}
hid_to_x.update({0x1e+i:10+i for i in range(10)})
for hids,codes in [([0x14,0x1a,8,0x15,0x17,0x1c,0x18,0x0c,0x12,0x13],range(24,34)),
                   ([4,0x16,7,9,0x0a,0x0b,0x0d,0x0e,0x0f,0x33,0x34],range(38,49)),
                   ([0x1d,0x1b,6,0x19,5,0x11,0x10,0x36,0x37,0x38],range(52,62))]:hid_to_x.update(zip(hids,codes))
roles={0x39:'Mod3_left',0x32:'Mod3_right',0x64:'Mod4_left',0xe6:'Mod4_right',0xe1:'Shift_left',0xe5:'Shift_right',
       0xff:'board_Fn1_preserved',0xfe:'board_Fn2_preserved',0x29:'Escape_preserved',0x2a:'Backspace_preserved',
       0xe0:'Control_left',0xe4:'Control_right',0xe2:'Alt_left',0xe3:'GUI_left'}
entries=json.loads((ROOT/'qmk_port/scan/function_layers.json').read_text())['layers'][0]['entries']
board=[]
for entry in entries:
    if entry['kind']=='absent':continue
    hid=entry['first_byte'];record={'bank':entry['bank'],'channel':entry['channel'],'original_logical_id':entry['original_key_id'],'physical_hid':hex(hid)}
    if hid in hid_to_x:record.update(canonical[str(hid_to_x[hid])])
    else:record['role']=roles[hid]
    board.append(record)
assert len(board)==62
data={'layout':'Canonical Neo2 six levels, data only','commit':manifest['commit'],
      'source_order_to_canonical':order,'canonical_keys':canonical,'physical_board_positions':board,
      'modifiers':{'Mod3':[[2,0],[5,8]],'Mod4':[[3,1],[4,4]],'Shift':[[3,0],[4,10]]},
      'missing_physical_key':{'xmodmap_keycode':49,'name':'T1 left of1','candidate_route':'Keep physical Esc; existing60%Fn+Esc route needs a separate policy.'},
      'sources':manifest['sources'],'license':{'driver_data':'GPLv3 per Neo project policy; COPYING retained','reference_text':'CC-BY-SA3.0Germany per Neo project policy',
                                             'keysym_header':'The Open Group/DEC permissive notices retained in downloaded header',
                                             'policy_url':'https://www.neo-layout.org/Beitragen/Lizenzfragen/'}}
(HERE/'canonical_neo2.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(HERE/'canonical_validation.json').write_text(json.dumps({'passed':True,'independent_reference_diagram_cells':len(checks),'reference_layers':6,
    'physical_board_keys':62,'unresolved_symbols':0,'checks':checks,'canonical_json_sha256':hashlib.sha256((HERE/'canonical_neo2.json').read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PASS: canonical6layers validated against276 independent reference-diagram cells;62 physical positions mapped.')
