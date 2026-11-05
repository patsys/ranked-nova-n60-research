"""Extract original fallback layers selected by momentary FF / FE actions."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[2]
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
geometry=json.loads((ROOT/'firmware_dump/key_scan_tables.json').read_text())
layers=[]
for layer,base in enumerate((0xf6a2,0xf79e,0xf89a)):
    entries=[]
    for bank in range(6):
        for channel,row in enumerate(geometry['logical_key_ids_by_channel_then_bank']):
            key=row[bank]
            first,second=flash[base+2*key:base+2*key+2]
            kind='absent' if key==1 else ('momentary_layer1' if first==0xff else 'momentary_layer2' if first==0xfe else 'vendor_action' if first==0xfb or 0xb0<=first<=0xbf else 'basic_hid_usage' if first<=0xa4 or 0xe0<=first<=0xe7 else 'unresolved')
            entries.append(dict(bank=bank,channel=channel,original_key_id=key,first_byte=first,second_byte=second,kind=kind))
    layers.append(dict(layer=layer,table_address=hex(base),entries=entries))
result=dict(evidence={'detect':'0x33a0','dispatch':'0x3598','layer1':'0x32f0','layer2':'0x3348'},
            behavior='Held FF selects alternate layer1, otherwise held FE selects layer2. FF has priority; selectors suppressed from normal report. Original mutable mappings and conditional timer behavior are separate.',layers=layers)
Path(__file__).with_name('function_layers.json').write_text(json.dumps(result,indent=2)+'\n')
print('Extracted 3 fallback layers, 66 geometry slots each; selectors FF/FE preserved as semantic actions.')
