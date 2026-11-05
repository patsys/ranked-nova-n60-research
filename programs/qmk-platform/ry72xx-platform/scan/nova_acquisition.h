// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once
#include "recovered_scan.h"

typedef struct {
    uint32_t (*read32)(uintptr_t address, void *context);
    void (*write32)(uintptr_t address, uint32_t value, void *context);
    void (*delay_original_units)(uint32_t units, void *context);
    void *context;
} nova_scan_io;

typedef struct {
    nova_scan_io io;
    uint16_t     samples[RANKED_BANKS][RANKED_CHANNELS];
    uint16_t     channel_bank_bits[RANKED_CHANNELS];
    bool         initialized;
} nova_acquisition;

/* Recovered original register sequence, with no flash controller operations.
 * CPU clock/reset setup must already have completed. Original acquisition
 * timing/thresholds are retained; physical hardware is not yet validated. */
bool nova_acquisition_init(nova_acquisition *state, const nova_scan_io *io);
/* Cold application initialization retains original long100-before-GPIO and
 * long300-after-GPIO ordering. Callback units are original dd80 units, not ms. */
bool     nova_acquisition_init_settled(nova_acquisition *state, const nova_scan_io *io, bool (*delay_original_long)(uint32_t, void *));
bool     nova_acquisition_scan(nova_acquisition *state);
void     nova_acquisition_rows(const nova_acquisition *state, uint16_t rows[RANKED_BANKS]);
uint32_t nova_scan_mmio_read32(uintptr_t address, void *context);
void     nova_scan_mmio_write32(uintptr_t address, uint32_t value, void *context);
