// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
#include <stdbool.h>

enum { NOVA_RGB_FRAME_BYTES = 269 };
typedef struct {
    uint32_t (*read32)(uintptr_t address);
    void (*write32)(uintptr_t address, uint32_t value);
    void (*delay_units)(uint32_t units);
    uint32_t (*ticks)(void);
} nova_rgb_io;
typedef struct {
    nova_rgb_io io;
    _Alignas(16) uint8_t tx[NOVA_RGB_FRAME_BYTES];
    _Alignas(16) uint8_t rx[NOVA_RGB_FRAME_BYTES];
    uint32_t started, submitted, completed, errors, skipped;
    bool     ready, active;
    uint8_t  last_reply;
} nova_rgb_transport;

bool nova_rgb_transport_init(nova_rgb_transport *state, const nova_rgb_io *io);
bool nova_rgb_transport_submit(nova_rgb_transport *state, const uint8_t colors[6][11][3]);
void nova_rgb_transport_poll(nova_rgb_transport *state);
void nova_rgb_pack(uint8_t frame[NOVA_RGB_FRAME_BYTES], const uint8_t colors[6][11][3]);
