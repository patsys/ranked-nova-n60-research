"""Cross-compile recovered components; never create/install a flashable image."""
from pathlib import Path
import hashlib, json, subprocess
ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT/'.build-tools/bin'
OUT = ROOT/'qmk_port/build'
OUT.mkdir(parents=True, exist_ok=True)

def run(args):
    return subprocess.run([str(a) for a in args], cwd=ROOT,
                          check=True, text=True, capture_output=True).stdout

sources = ['platform/recovered_clock.c', 'scan/recovered_scan.c',
           'usb/ranked_usb_io.c', 'keyboard/keymaps/default/keymap.c']
flags = ['-mcpu=cortex-m0', '-mthumb', '-std=c11', '-Os', '-g',
         '-ffreestanding', '-fno-common', '-Wall', '-Wextra', '-Werror']
records = []; objects = []
for name in sources:
    src = ROOT/'qmk_port'/name
    obj = OUT/(src.stem+'.o')
    command = [TOOLS/'arm-none-eabi-gcc.exe', *flags]
    if name.endswith('/keymap.c'):
        command += ['-I', ROOT/'qmk_port/keyboard',
                    '-I', ROOT/'qmk_source/platforms',
                    '-I', ROOT/'qmk_source/quantum',
                    '-DQMK_KEYBOARD_H="component_keymap_types.h"']
    command += ['-c', src, '-o', obj]
    run(command); objects.append(obj)
    records.append(dict(source=name, object=obj.name,
                        source_sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
archive = OUT/'libnova_recovered.a'
if archive.exists(): archive.unlink()  # Rebuild this one generated artifact.
run([TOOLS/'arm-none-eabi-ar.exe','rcs',archive,*objects])
# Standalone clock test ELF has no vector table/startup and is not an image.
clock_elf = OUT/'clock_validation.elf'
run([TOOLS/'arm-none-eabi-gcc.exe',*flags,'-nostdlib',
     '-Wl,-Ttext=0x18000,-e,nova_original_clock_setup',objects[0],'-o',clock_elf])
run([TOOLS/'arm-none-eabi-objcopy.exe','-O','binary',clock_elf,OUT/'clock_validation.bin'])
symbols = run([TOOLS/'arm-none-eabi-nm.exe','-n',clock_elf])
(OUT/'clock_validation.nm').write_text(symbols,encoding='utf-8')
report = dict(kind='ARM component archive plus offline clock-test ELF, not QMK firmware',
              target='Cortex-M0 Thumb instruction baseline; exact core still unconfirmed',
              compiler=run([TOOLS/'arm-none-eabi-gcc.exe','--version']).splitlines()[0],
              compiled=records, archive=archive.name,
              sizes=run([TOOLS/'arm-none-eabi-size.exe',*objects]),
              missing='Complete platform startup/vector handling, clock semantics, QMK USB HAL and custom matrix runtime; no firmware linking or flashing')
(OUT/'build_result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
