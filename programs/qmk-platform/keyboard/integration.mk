# Source fragment for a future verified platform/keyboard definition.
# This is not a selectable QMK keyboard yet: MCU/startup/HAL are unresolved.
# The custom matrix backend must consume analog samples into six 11-bit rows.
CUSTOM_MATRIX = lite
SRC += $(NOVA_PORT_DIR)/scan/recovered_scan.c
SRC += $(NOVA_PORT_DIR)/platform/recovered_clock.c
# Do not enable VIA/EEPROM until storage and USB raw-HID are implemented.
