"""Describe already-built ELF and evidence without recompiling or device access."""
from pathlib import Path
import argparse,json,hashlib,struct
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--via',action='store_true');parser.add_argument('--diagnostic',action='store_true');parser.add_argument('--keymap',choices=['default','neo2'],default='default');parser.add_argument('--rgb',action='store_true');args=parser.parse_args()
OUT=ROOT/(('qmk_port/build/firmware_via' if args.via else 'qmk_port/build/firmware')+('_diagnostic' if args.diagnostic else '')+('_neo2' if args.keymap=='neo2' else ''))
if args.rgb:OUT=OUT.with_name(OUT.name+'_rgb')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
build=json.loads((OUT/'build_progress.json').read_text())
assert build['link_success'] and not build['failures']
elf=OUT/'nova_qmk_research.elf'
validation=json.loads((OUT/'elf_validation.json').read_text())
assert validation['passed'] and validation['elf_sha256']==digest(elf)
symbols={}
for line in (OUT/'nova_qmk_research.nm').read_text().splitlines():
 p=line.split()
 if len(p)==3:symbols[p[2]]=int(p[0],16)
crt=ROOT/'qmk_source/lib/chibios/os/common/startup/ARMCMx/compilers/GCC'
startup=[dict(source=str(p.relative_to(ROOT)),sha256=digest(p))
         for p in [crt/'crt0_v6m.S',crt/'vectors.S',crt/'crt1.c',
                   ROOT/'qmk_port/platform/cmparams.h',ROOT/'qmk_port/platform/NOVA_RESEARCH.ld']]
artifacts=[dict(file=p.name,bytes=p.stat().st_size,sha256=digest(p)) for p in
           [elf,OUT/'nova_qmk_research.map',OUT/'nova_qmk_research.nm',OUT/'build_progress.json',OUT/'elf_validation.json']]
manifest=dict(kind='VIA-enabled QMK research firmware ELF' if args.via else 'QMK research firmware ELF',
              hardware_tested=False,installed=False,via_enabled=args.via,
              usb_diagnostic=args.diagnostic,
              keymap=args.keymap,rgb_enabled=args.rgb,
              keymap_sources=[dict(source=str(p.relative_to(ROOT)),sha256=digest(p)) for p in (ROOT/('qmk_port/keyboard/keymaps/'+args.keymap)).glob('*') if p.suffix in {'.c','.h','.mk'}],
              elf_sha256=digest(elf),artifacts=artifacts,
              compiled_sources=build['compiled'],startup_sources=startup,
              configuration_headers=[dict(source=str(p.relative_to(ROOT)),sha256=digest(p)) for p in
                 [ROOT/'qmk_port/keyboard/config.h',ROOT/'qmk_port/runtime/emergency_boot.h',
                  ROOT/'qmk_port/runtime/usb_diagnostic.h',
                  ROOT/'qmk_port/platform/atomic_util.h',ROOT/'qmk_port/platform/version.h']],
              qmk_revision='f5db962110615fd263c3ebf9f0402e7c2b08fbe4',
              compiler='Arm GNU Toolchain14.3.Rel1 GCC14.3.1',
              instruction_baseline='ARMv6-M Cortex-M0 Thumb; exact MCU/core not identified',
              flash_load_window=['0x2000','0x1a000'],ram_allocation_window=['0x20000000','0x20001c50'],
              variable_data_bytes=symbols['__data_end__']-symbols['__data_base__'],
              variable_bss_bytes=symbols['__bss_end__']-symbols['__bss_base__'],
              main_exception_stack_bytes=symbols['__main_stack_size__'],
              process_stack_bytes=symbols['__process_stack_size__'],
              remaining_heap_bytes=symbols['__heap_end__']-symbols['__heap_base__'],
              transient_eeprom_bytes=build.get('transient_bytes',128),
              storage_persistence='RAM only; power loss/reset loses changes',
              link_diagnostics=build['link_diagnostics'],
              validation='Actual startup reaches main; initialized data/BSS;27 original boot exception-forwarding cases',
              limitations=['No physical keyboard enumeration/typing test','No install/boot-acceptance test',
                           'Nominal48MHz clock not measured','Stack budgets not physical worst-case measurements'])
if args.rgb:
    p=ROOT/'qmk_port/rgb/nova_rgb_transport.h'
    manifest['configuration_headers'].append(dict(source=str(p.relative_to(ROOT)),sha256=digest(p)))
(OUT/'firmware_manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({k:manifest[k] for k in ['kind','elf_sha256','variable_data_bytes','variable_bss_bytes','remaining_heap_bytes']},indent=2))
