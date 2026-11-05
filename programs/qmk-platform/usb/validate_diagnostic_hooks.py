"""Compile diagnostic runtime variants; no hardware or firmware targets."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
# Reuse the established production include paths and compile definitions only.
scope={'__file__':str(ROOT/'qmk_port/usb/validate_controller_delays.py')}
text=(ROOT/'qmk_port/usb/validate_controller_delays.py').read_text()
exec(text[:text.index("source=P/'runtime/usb_keyboard.c'")],scope)
flags=scope['flags'];tools=scope['TOOLS'];out=ROOT/'qmk_port/usb/diagnostic_validation';out.mkdir(exist_ok=True)
results=[]
for via in (False,True):
    extra=['-DVIA_ENABLE','-DDYNAMIC_KEYMAP_ENABLE','-DRAW_ENABLE','-DDYNAMIC_KEYMAP_LAYER_COUNT=3','-DRAW_EPSIZE=32'] if via else []
    paths=[]
    for name,source,diag in [('before',ROOT/'qmk_port/usb/usb_keyboard_before_diagnostic.c.txt',False),('default',ROOT/'qmk_port/runtime/usb_keyboard.c',False),('diagnostic',ROOT/'qmk_port/runtime/usb_keyboard.c',True)]:
        obj=out/(('via_' if via else 'basic_')+name+'.o')
        subprocess.run([str(tools/'arm-none-eabi-gcc.exe'),*[str(x) for x in flags],*extra,*(['-DNOVA_USB_DIAGNOSTIC'] if diag else []),'-x','c','-c',str(source),'-o',str(obj)],check=True)
        paths.append(obj)
    # Source basename changes ELF file symbol, so compare executable sections.
    sections={}
    for obj in paths:
        dump=subprocess.check_output([str(tools/'arm-none-eabi-objdump.exe'),'-d',str(obj)],text=True)
        sections[obj.stem]='\n'.join(dump.splitlines()[3:])
    assert list(sections.values())[0]==list(sections.values())[1]
    undefined=subprocess.check_output([str(tools/'arm-none-eabi-nm.exe'),'-u',str(paths[2])],text=True)
    hooks=['nova_usb_diagnostic_'+x for x in ('irq','status','event','configured','aux')]
    assert all(x in undefined for x in hooks)
    results.append({'via':via,'default_executable_sections_unchanged':True,'diagnostic_hooks':hooks,'objects':[str(x.relative_to(ROOT)) for x in paths]})
(out/'validation.json').write_text(json.dumps({'hardware_access':False,'variants':results},indent=2))
print('Default executable sections unchanged; basic/VIA diagnostic variants compile with all five hooks')
