# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later

# The flasher is a separate host program, like dfu-util and mdloader. Do not
# substitute a generic Cortex-M flashing tool: this bootloader has its own
# protocol and application layout.
RY72XX_FLASHER ?= ry72xx-flasher
RY72XX_FLASHER_ARGS ?=

.PHONY: flash ry72xx
flash: $(BUILD_DIR)/$(TARGET).hex cpfirmware sizeafter
	$(SILENT) || printf "Flashing for bootloader: RY7203 vendor HID\n"
ifneq ($(strip $(PROGRAM_CMD)),)
	$(UNSYNC_OUTPUT_CMD) && $(PROGRAM_CMD)
else
	$(RY72XX_FLASHER) $(RY72XX_FLASHER_ARGS) --mcu RY7203 --file "$(BUILD_DIR)/$(TARGET).hex"
endif

ry72xx: flash
