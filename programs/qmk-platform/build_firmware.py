"""Compile real QMK sources with recovered hardware; no device access.

This custom build intentionally reports unresolved platform work rather than
inventing dummy implementations. Its linked artifact, when complete, is for
offline research only, not an installation recommendation.
"""
from pathlib import Path
import subprocess, json, hashlib, argparse
parser=argparse.ArgumentParser()
parser.add_argument('--via',action='store_true',help='Build actual VIA and RAM-only dynamic keymap support separately')
parser.add_argument('--diagnostic',action='store_true',help='Build separate bounded USB diagnostic variant')
parser.add_argument('--keymap',choices=['default','neo2'],default='default')
parser.add_argument('--rgb',action='store_true',help='Separate custom RGB Matrix lighting trial')
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/'qmk_source';P=ROOT/'qmk_port';OUT=P/(('build/firmware_via' if args.via else 'build/firmware')+('_diagnostic' if args.diagnostic else '')+('_neo2' if args.keymap=='neo2' else ''));OUT.mkdir(parents=True,exist_ok=True)
BIN=ROOT/'.build-tools/bin'
if args.rgb:
    OUT=OUT.with_name(OUT.name+'_rgb');OUT.mkdir(parents=True,exist_ok=True)
sources=['quantum/quantum.c','quantum/bitwise.c','quantum/led.c',
 'quantum/action.c','quantum/action_layer.c','quantum/action_tapping.c',
 'quantum/action_util.c','quantum/eeconfig.c','quantum/keyboard.c',
 'quantum/keymap_common.c','quantum/keycode_config.c','quantum/sync_timer.c',
 'quantum/logging/debug.c','quantum/logging/sendchar.c',
 'quantum/process_keycode/process_default_layer.c',
 'quantum/process_keycode/process_oneshot.c','quantum/process_keycode/process_quantum.c',
 'quantum/keymap_introspection.c','quantum/nvm/eeprom/nvm_eeconfig.c',
 'tmk_core/protocol/host.c','tmk_core/protocol/report.c','tmk_core/protocol/usb_device_state.c',
 'platforms/timer.c','platforms/suspend.c','quantum/logging/print.c',
 'drivers/eeprom/eeprom_transient.c','drivers/eeprom/eeprom_driver.c',
 'quantum/matrix_common.c','quantum/debounce/sym_defer_g.c']
if args.via:
    sources += ['quantum/via.c','quantum/dynamic_keymap.c','quantum/raw_hid.c',
                'quantum/nvm/eeprom/nvm_via.c','quantum/nvm/eeprom/nvm_dynamic_keymap.c',
                'quantum/send_string/send_string.c']
if args.keymap=='neo2':sources += ['quantum/process_keycode/process_key_override.c']
if args.rgb:
    sources += ['quantum/process_keycode/process_underglow.c','quantum/process_keycode/process_rgb_matrix.c',
                'quantum/color.c','quantum/led_tables.c','quantum/rgb_matrix/rgb_matrix.c',
                'quantum/rgb_matrix/rgb_matrix_drivers.c','lib/lib8tion/lib8tion.c']
# Only real platform/driver implementations are added as they become available.
local=['platform/recovered_clock.c','platform/original_delay.c','platform/original_delay_loop.S',
       'scan/recovered_scan.c','scan/nova_acquisition.c','keyboard/matrix.c',
       'usb/ranked_usb_io.c','usb/ranked_usb_device.c']
local += [str(x.relative_to(P)).replace('\\','/') for x in sorted((P/'runtime').glob('*.c'))]
if args.rgb:local += ['rgb/nova_rgb_transport.c','rgb/nova_rgb_matrix.c','rgb/nova_rgb_layout.c']
includes=[Q/'platforms',P/'platform',Q/'quantum',Q/'quantum/keymap_extras',
 Q/'quantum/logging',Q/'quantum/process_keycode',Q/'quantum/nvm',
 Q/'quantum/nvm/eeprom',Q/'tmk_core/protocol',Q/'tmk_core/common',Q/'lib/printf/src',
 P/'keyboard',P/('keyboard/keymaps/'+args.keymap),Q/'quantum/debounce',Q/'quantum/sequencer',
 Q/'drivers/eeprom',P/'runtime',P/'usb',P/'scan',Q/'quantum/send_string']
flags=['-mcpu=cortex-m0','-mthumb','-std=gnu11','-Os','-g','-ffreestanding',
 '-fno-common','-ffunction-sections','-fdata-sections','-fshort-enums',
 '-Wall','-Wextra','-include',P/'keyboard/config.h',
 '-DQMK_KEYBOARD_H="research_keyboard.h"','-DKEYMAP_C="keymap.c"',
 '-DNO_PRINT','-DNO_DEBUG','-DNVM_DRIVER_EEPROM','-DEEPROM_DRIVER="transient"',
 '-DEEPROM_TRANSIENT',f'-DTRANSIENT_EEPROM_SIZE={1024 if args.via else 128}',
 '-DNO_ACTION_ONESHOT','-DNO_ACTION_TAPPING','-DNO_USB_STARTUP_CHECK',
 '-DKEYBOARD_NAME="ranked/nova_research"','-DKEYMAP_NAME="default"']
if args.diagnostic: flags += ['-DNOVA_USB_DIAGNOSTIC']
if args.rgb:
    flags += ['-DRGB_MATRIX_ENABLE','-DRGB_MATRIX_CUSTOM','-DUSE_CIE1931_CURVE',
              '-include',Q/'quantum/rgb_matrix/post_config.h','-I',Q,'-I',P/'rgb',
              '-I',Q/'quantum/rgb_matrix','-I',Q/'quantum/rgb_matrix/animations',
              '-I',Q/'quantum/rgb_matrix/animations/runners']
if args.keymap=='neo2':flags += ['-DKEY_OVERRIDE_ENABLE']
if args.via:
    flags += ['-DVIA_ENABLE','-DDYNAMIC_KEYMAP_ENABLE','-DRAW_ENABLE',
              '-DDYNAMIC_KEYMAP_LAYER_COUNT=3','-DRAW_EPSIZE=32']
for inc in includes:flags+=['-I',inc]
records=[];objects=[];failures=[]
for src in [Q/x for x in sources]+[P/x for x in local]:
    obj=OUT/('_'.join(src.relative_to(ROOT).parts).replace('.','_')+'.o')
    cmd=[BIN/'arm-none-eabi-gcc.exe',*flags,'-c',src,'-o',obj]
    proc=subprocess.run([str(x) for x in cmd],cwd=ROOT,text=True,capture_output=True)
    records.append(dict(source=str(src.relative_to(ROOT)),success=proc.returncode==0,
                        sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
    if proc.returncode:failures.append(dict(source=str(src.relative_to(ROOT)),diagnostic=proc.stderr))
    else:objects.append(obj)
report=dict(kind='Actual QMK custom-platform compilation progress, not complete firmware',
            compiled=records,failures=failures,compiled_count=len(objects),source_count=len(records),
            via_enabled=args.via,keymap=args.keymap,rgb_enabled=args.rgb,storage='RAM-only transient EEPROM',transient_bytes=1024 if args.via else 128)
(OUT/'build_progress.json').write_text(json.dumps(report,indent=2))
if not failures:
    combined=OUT/'quantum_research_combined.o'
    subprocess.run([str(BIN/'arm-none-eabi-ld.exe'),'-r',*[str(x) for x in objects],'-o',str(combined)],check=True)
    symbols=subprocess.run([str(BIN/'arm-none-eabi-nm.exe'),'-u',str(combined)],check=True,capture_output=True,text=True).stdout
    (OUT/'unresolved_symbols.txt').write_text(symbols)
    crt=Q/'lib/chibios/os/common/startup/ARMCMx/compilers/GCC'
    startup_flags=['-DCRT0_VTOR_INIT=FALSE','-DCRT0_INIT_VECTORS=FALSE','-DCRT0_AREAS_NUMBER=1']
    for src in [crt/'crt0_v6m.S',crt/'vectors.S',crt/'crt1.c']:
        obj=OUT/(src.stem+'.o')
        subprocess.run([str(x) for x in [BIN/'arm-none-eabi-gcc.exe',*flags,*startup_flags,'-c',src,'-o',obj]],check=True)
        objects.append(obj)
    elf=OUT/'nova_qmk_research.elf'
    link=[BIN/'arm-none-eabi-gcc.exe','-mcpu=cortex-m0','-mthumb','-nostdlib',
          '-Wl,--gc-sections,--no-warn-rwx-segments',
          '-Wl,--defsym=__main_stack_size__=0x200,--defsym=__process_stack_size__=0x400',
          '-Wl,-L'+str(crt/'ld'),'-Wl,-Map='+str(OUT/'nova_qmk_research.map'),
          '-T',P/'platform/NOVA_RESEARCH.ld',*objects,'-Wl,--start-group','-lc','-lgcc','-lnosys','-Wl,--end-group','-o',elf]
    linked=subprocess.run([str(x) for x in link],cwd=ROOT,text=True,capture_output=True)
    report['link_success']=linked.returncode==0
    report['link_diagnostics']=linked.stderr
    if linked.returncode:
        failures.append(dict(stage='link',diagnostic=linked.stderr))
    else:
        report['elf']=str(elf.relative_to(ROOT))
        report['kind']='Real QMK core linked with recovered custom platform; offline research ELF, not hardware validated'
        report['size']=subprocess.run([str(BIN/'arm-none-eabi-size.exe'),str(elf)],check=True,capture_output=True,text=True).stdout
        report['symbols']=subprocess.run([str(BIN/'arm-none-eabi-nm.exe'),'-n',str(elf)],check=True,capture_output=True,text=True).stdout
        (OUT/'nova_qmk_research.nm').write_text(report.pop('symbols'))
    report['failures']=failures
    (OUT/'build_progress.json').write_text(json.dumps(report,indent=2))
print(json.dumps(dict(compiled_count=len(records)-sum(not r['success'] for r in records),
                     source_count=len(records),link_success=report.get('link_success',False),
                     first_errors=failures[:3]),indent=2))
raise SystemExit(bool(failures))
