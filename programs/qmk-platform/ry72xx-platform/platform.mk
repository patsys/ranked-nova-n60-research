# Copyright 2026 patsys
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
LDFLAGS += $(MCUFLAGS) -nostdlib -Wl,--gc-sections
LDFLAGS += -Wl,--defsym=__main_stack_size__=0x200,--defsym=__process_stack_size__=0x400
LDFLAGS += -L$(RY72XX_CRT)/ld -T$(RY72XX_DIR)/nova_research.ld
EXTRALDFLAGS += -Wl,--start-group -lc -lgcc -lnosys -Wl,--end-group
FIRMWARE_FORMAT = hex

# Only implemented report types may be enabled.
ifneq ($(filter yes,$(MOUSEKEY_ENABLE) $(EXTRAKEY_ENABLE) $(CONSOLE_ENABLE)),)
    $(error RY7203 does not yet support mouse, media or console reports)
endif
SRC += $(RY72XX_DIR)/syscalls.c

ifeq ($(EEPROM_DRIVER),wear_leveling)
ifeq ($(WEAR_LEVELING_DRIVER),custom)
    SRC += $(RY72XX_DIR)/drivers/wear_leveling/wear_leveling_nova_flash.c
endif
endif

ifeq ($(strip $(RAW_ENABLE)),yes)
    OPT_DEFS += -DRAW_EPSIZE=32
endif
