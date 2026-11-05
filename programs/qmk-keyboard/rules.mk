# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
CUSTOM_MATRIX = lite
MCU = RY7203
EEPROM_DRIVER = wear_leveling
WEAR_LEVELING_DRIVER = custom
OPT_DEFS += -DBACKING_STORE_WRITE_SIZE=4
OPT_DEFS += -DWEAR_LEVELING_BACKING_SIZE=4096
OPT_DEFS += -DWEAR_LEVELING_LOGICAL_SIZE=1024
NO_USB_STARTUP_CHECK = yes
SRC += platforms/ry72xx/scan/matrix.c platforms/ry72xx/scan/emergency_boot.c

SRC += rgb/nova_rgb_transport.c rgb/nova_rgb_matrix.c rgb/nova_rgb_layout.c
VPATH += keyboards/ranked/nova_n60/rgb
