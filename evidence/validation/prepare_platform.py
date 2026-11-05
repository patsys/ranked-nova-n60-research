"""Stage an allowlisted, source-only experimental QMK platform contribution."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
Q = ROOT / 'contributions/qmk_firmware'
P = ROOT / 'qmk_port'
license_header = '// Copyright 2026 patsys\n// SPDX-License-Identifier: GPL-3.0-or-later\n\n'

def write(path, text):
    path = Q / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace('\r\n', '\n'), encoding='utf-8', newline='\n')

for folder, names in {
    'platform': ['recovered_clock.c', 'recovered_clock.h', 'original_delay.c', 'original_delay_loop.S', 'cmparams.h', 'NOVA_RESEARCH.ld', '_pin_defs.h', '_timer.h', '_wait.h', 'atomic_util.h', 'platform_deps.h'],
    'scan': ['recovered_scan.c', 'recovered_scan.h', 'nova_acquisition.c', 'nova_acquisition.h'],
    'usb': ['ranked_usb_io.c', 'ranked_usb_io.h', 'ranked_usb_device.c', 'ranked_usb_device.h'],
    'runtime': ['timebase.c', 'usb_keyboard.c', 'usb_diagnostic.c', 'usb_diagnostic.h', 'emergency_boot.c', 'emergency_boot.h'],
}.items():
    for name in names:
        dest = 'platforms/ry72xx/' + (name if folder == 'platform' else folder + '/' + name)
        text = (P / folder / name).read_text()
        text = text.replace('../platform/', '../')
        if not ('SPDX-License-Identifier' in text or 'Licensed under the Apache License' in text):
            text = license_header + text
        write(dest, text)

write('platforms/ry72xx/mcu_selection.mk', '''# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
ifeq ($(strip $(MCU)),RY7203)
    PLATFORM_KEY = ry72xx
    MCU_ARCH = cortex-m0
    MCU_FAMILY = RY72XX
endif
''')
write('platforms/ry72xx/platform.mk', '''# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
TOOLCHAIN ?= arm-none-eabi-
CC = $(CC_PREFIX) $(TOOLCHAIN)gcc
OBJCOPY = $(TOOLCHAIN)objcopy
OBJDUMP = $(TOOLCHAIN)objdump
SIZE = $(TOOLCHAIN)size
AR = $(TOOLCHAIN)ar
NM = $(TOOLCHAIN)nm
HEX = $(OBJCOPY) -O $(FORMAT)
BIN = $(OBJCOPY) -O binary
EEP =
MCUFLAGS = -mcpu=cortex-m0 -mthumb
CFLAGS += -ffreestanding -fno-common -ffunction-sections -fdata-sections -fshort-enums
ASFLAGS += -DCRT0_VTOR_INIT=FALSE -DCRT0_INIT_VECTORS=FALSE -DCRT0_AREAS_NUMBER=1
OPT_DEFS += -DCRT0_VTOR_INIT=FALSE -DCRT0_INIT_VECTORS=FALSE -DCRT0_AREAS_NUMBER=1 -DNO_USB_STARTUP_CHECK
RY72XX_DIR = $(PLATFORM_PATH)/ry72xx
RY72XX_CRT = lib/chibios/os/common/startup/ARMCMx/compilers/GCC
SRC := $(filter-out $(RY72XX_DIR)/hardware_id.c $(RY72XX_DIR)/suspend.c $(RY72XX_DIR)/timer.c $(RY72XX_DIR)/bootloaders/%.c,$(SRC))
SRC += $(RY72XX_DIR)/recovered_clock.c $(RY72XX_DIR)/original_delay.c $(RY72XX_DIR)/original_delay_loop.S
SRC += $(RY72XX_DIR)/runtime/timebase.c $(RY72XX_DIR)/runtime/usb_diagnostic.c
SRC += $(RY72XX_DIR)/scan/recovered_scan.c $(RY72XX_DIR)/scan/nova_acquisition.c
SRC += $(RY72XX_CRT)/crt0_v6m.S $(RY72XX_CRT)/vectors.S $(RY72XX_CRT)/crt1.c
VPATH += $(RY72XX_DIR) $(RY72XX_DIR)/runtime $(RY72XX_DIR)/scan $(RY72XX_DIR)/usb
LDFLAGS += $(MCUFLAGS) -nostdlib -Wl,--gc-sections,--no-warn-rwx-segments
LDFLAGS += -Wl,--defsym=__main_stack_size__=0x200,--defsym=__process_stack_size__=0x400
LDFLAGS += -L$(RY72XX_CRT)/ld -T$(RY72XX_DIR)/NOVA_RESEARCH.ld
EXTRALDFLAGS += -Wl,--start-group -lc -lgcc -lnosys -Wl,--end-group
FIRMWARE_FORMAT = hex
''')
write('tmk_core/protocol/ry72xx/ry72xx.mk', '''# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
SRC += platforms/ry72xx/runtime/usb_keyboard.c
SRC += platforms/ry72xx/usb/ranked_usb_io.c platforms/ry72xx/usb/ranked_usb_device.c
''')

# Keep the normal QMK main loop; implement its platform/protocol hooks.
main = (P / 'runtime/main.c').read_text()
setup = main.split('int main(void) {', 1)[1].split('nova_usb_diagnostic_mark(NOVA_DIAG_STAGE_KEYBOARD_SETUP)', 1)[0]
post = main.split('if (nova_matrix_initialization_failed)', 1)[1].split('nova_usb_diagnostic_mark(NOVA_DIAG_STAGE_MAIN_LOOP);', 1)[0]
write('platforms/ry72xx/platform.c', license_header + '''#include <stdbool.h>
#include <stdint.h>
#include "keyboard.h"
#include "recovered_clock.h"
#include "emergency_boot.h"
#include "usb_diagnostic.h"
extern bool nova_usb_keyboard_init(void);
extern void nova_usb_keyboard_task(void);
extern volatile bool nova_matrix_initialization_failed;
extern void nova_platform_delay_original_units(uint32_t);
extern int nova_platform_delay_original_long(uint32_t);
volatile unsigned nova_runtime_failure;
void platform_setup(void) {''' + setup + '''}
void protocol_setup(void) {}
void protocol_pre_init(void) {}
void protocol_post_init(void) {
    if (nova_matrix_initialization_failed)''' + post + '''}
void protocol_pre_task(void) {}
void protocol_post_task(void) { nova_usb_keyboard_task(); }
''')

board = 'keyboards/ranked/nova_n60'
text = (P / 'keyboard/matrix.c').read_text().replace('../scan/nova_acquisition.h', 'nova_acquisition.h')
write(board + '/matrix.c', license_header + text)
text = (P / 'runtime/emergency_boot.c').read_text().replace('../scan/recovered_scan.h', 'recovered_scan.h')
write(board + '/emergency_boot.c', license_header + text)
# Emergency key scanning is keyboard-specific, not a general MCU service.
(Q / 'platforms/ry72xx/runtime/emergency_boot.c').unlink()
write(board + '/config.h', license_header + '''#pragma once
#define MATRIX_ROWS 6
#define MATRIX_COLS 11
#define NOVA_SCAN_CONVERSION_SETTLE_UNITS 20
#define NOVA_EMERGENCY_HOLD_MODE 2
#define NOVA_EMERGENCY_HOLD_SCANS 3
''')
write(board + '/rules.mk', '''# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
CUSTOM_MATRIX = lite
EEPROM_DRIVER = transient
NO_USB_STARTUP_CHECK = yes
SRC += emergency_boot.c
''')
write(board + '/keymaps/default/keymap.c', license_header + (P / 'keyboard/keymaps/default/keymap.c').read_text())

# Physical ISO layout, in visual order; matrix bank 5 contains the row ends.
rows = [
    [(0,c) for c in range(11)] + [(5,1),(5,2),(5,3)],
    [(1,c) for c in range(11)] + [(5,4),(5,5)],
    [(2,c) for c in range(11)] + [(5,7),(5,8),(5,9)],
    [(3,c) for c in range(11)] + [(4,8),(4,10)],
    [(4,c) for c in range(8)],
]
widths = [[1]*13+[2], [1.5]+[1]*12, [1.75]+[1]*12+[1.25], [1.25]+[1]*11+[2.75], [1.25]*3+[6.25]+[1.25]*4]
layout = []
for y, row in enumerate(rows):
    x = 0
    for i, pos in enumerate(row):
        w = widths[y][i]
        layout.append(dict(matrix=list(pos),x=x,y=y,w=w))
        x += w
info = dict(keyboard_name='Ranked Nova N60', manufacturer='Ranked', maintainer='patsys',
    processor='RY7203', bootloader='custom', usb=dict(vid='0x3532',pid='0xA0A3',device_version='1.0.0'),
    features=dict(bootmagic=False,console=False,extrakey=False,mousekey=False,nkro=False),
    matrix_pins=dict(custom_lite=True), layouts={'LAYOUT':dict(layout=layout)})
write(board + '/keyboard.json', json.dumps(info, indent=4)+'\n')

# The one-key target uses the same analog front end on a Nova; it is not a
# claim of a standalone development board or unverified digital GPIO support.
test = 'keyboards/handwired/onekey/ry7203'
onekey = dict(info)
onekey.update(keyboard_name='RY7203 Nova one-key test', layouts={'LAYOUT_ortho_1x1':dict(layout=[dict(matrix=[0,0],x=0,y=0)])})
write(test + '/keyboard.json', json.dumps(onekey,indent=4)+'\n')
write(test + '/config.h', license_header + (Q / board / 'config.h').read_text().split('#pragma once',1)[1].join(['#pragma once','']))
write(test + '/rules.mk', (Q / board / 'rules.mk').read_text() + 'SRC += keyboards/ranked/nova_n60/matrix.c keyboards/ranked/nova_n60/emergency_boot.c\n')
write(test + '/keymaps/default/keymap.c', license_header + '#include QMK_KEYBOARD_H\nconst uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = { [0] = LAYOUT_ortho_1x1(KC_A) };\n')

schema = Q / 'data/schemas/keyboard.jsonschema'
text = schema.read_text().replace('"cortex-m0",', '"RY7203",\n                "cortex-m0",',1)
schema.write_text(text,encoding='utf-8',newline='\n')
path = Q / 'lib/python/qmk/info.py'
text = path.read_text().replace("if info_data['processor'] in CHIBIOS_PROCESSORS:", "if info_data['processor'] == 'RY7203':\n        info_data.update(processor_type='arm', protocol='RY72XX', platform_key='ry72xx', platform='RY72XX')\n\n    elif info_data['processor'] in CHIBIOS_PROCESSORS:")
path.write_text(text,encoding='utf-8',newline='\n')
print('Staged experimental RY7203 platform, normal QMK hooks and source-only test targets.')
