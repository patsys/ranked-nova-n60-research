// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <stdbool.h>
#include <stdint.h>

#define NOVA_FLASH_BACKING_BYTES 4096u
#define NOVA_FLASH_WRITE_BYTES 4u

static inline bool nova_flash_address_valid(uint32_t address) {
    return address <= NOVA_FLASH_BACKING_BYTES - NOVA_FLASH_WRITE_BYTES && (address % NOVA_FLASH_WRITE_BYTES) == 0u;
}
