// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later
#include "nova_rgb_transport.h"
#include <string.h>

/* Reimplemented from original 5A64/E598 and 3BF8/5A74/E558 behavior.
 * SPI route codes are observed encoded values, not guessed package pins.
 * No flash, retained boot flag, arbitrary register or interrupt handler API.
 */
static uint32_t read_reg(nova_rgb_transport *s, uintptr_t a) {
    return s->io.read32(a);
}
static void write_reg(nova_rgb_transport *s, uintptr_t a, uint32_t v) {
    s->io.write32(a, v);
}
static void acknowledge(nova_rgb_transport *s) {
    write_reg(s, 0x40005008, 7);
    write_reg(s, 0x40005010, read_reg(s, 0x40005010) & ~0x60u);
}
bool nova_rgb_transport_init(nova_rgb_transport *s, const nova_rgb_io *io) {
    if (!s || !io || !io->read32 || !io->write32 || !io->delay_units || !io->ticks) return false;
    memset(s, 0, sizeof(*s));
    s->io = *io;
    write_reg(s, 0x4001402c, 0x20);
    io->delay_units(10);
    write_reg(s, 0xe000e180, 0x800); /* Original driver polls; keep IRQ11 disabled. */
    if (read_reg(s, 0x4000504c) & 8u) return false;
    write_reg(s, 0x40005004, 0);
    write_reg(s, 0x40005008, 7);
    write_reg(s, 0x4000500c, 0);
    io->delay_units(20);
    write_reg(s, 0x40005034, 0x46);
    write_reg(s, 0x40005038, 0x44);
    write_reg(s, 0x4000503c, 0x42);
    write_reg(s, 0x40005040, 0x47);
    write_reg(s, 0x40005014, 3); /* Original nominal48MHz / 8MHz / 2. */
    write_reg(s, 0x40005020, 0);
    write_reg(s, 0x4000501c, 5);
    write_reg(s, 0x40005024, 0);
    write_reg(s, 0x40005010, 0x11);
    write_reg(s, 0x40005028, 0x3fff);
    write_reg(s, 0x4000500c, 1);
    write_reg(s, 0xe000e180, 0x800);
    write_reg(s, 0x40005004, 7);
    s->ready = true;
    return true;
}
void nova_rgb_pack(uint8_t frame[NOVA_RGB_FRAME_BYTES], const uint8_t colors[6][11][3]) {
    memset(frame, 0, NOVA_RGB_FRAME_BYTES);
    /* Enabled stock level9 uses250, not the6250 fallback path. QMK scales
     * channel values for brightness; retain this native enabled timing field. */
    frame[0] = 0xc0;
    frame[1] = 11;
    frame[2] = 6;
    frame[4] = 0xfa;
    for (unsigned plane = 0; plane < 3; ++plane)
        for (unsigned channel = 0; channel < 11; ++channel)
            for (unsigned bank = 0; bank < 6; ++bank)
                frame[6 + plane * 88 + channel * 8 + bank] = colors[bank][channel][plane];
}
void nova_rgb_transport_poll(nova_rgb_transport *s) {
    if (!s || !s->ready || !s->active) return;
    uint32_t status = read_reg(s, 0x4000504c);
    if (status & 1u) {
        acknowledge(s);
        s->active     = false;
        s->last_reply = s->rx[0];
        if (!(status & 6u) && s->last_reply == 0xa5)
            ++s->completed;
        else
            ++s->errors;
    } else if ((uint32_t)(s->io.ticks() - s->started) >= 10u) {
        /* Stop requests before releasing the DMA-owned buffers on timeout. */
        acknowledge(s);
        ++s->errors;
        s->started = s->io.ticks();
        /* A busy peripheral may still own the buffers: do not reuse them. */
        if (!(read_reg(s, 0x4000504c) & 8u)) s->active = false;
    }
}
bool nova_rgb_transport_submit(nova_rgb_transport *s, const uint8_t colors[6][11][3]) {
    if (!s || !colors || !s->ready) return false;
    nova_rgb_transport_poll(s);
    if (s->active || (read_reg(s, 0x4000504c) & 8u)) {
        ++s->skipped;
        return false;
    }
    nova_rgb_pack(s->tx, colors);
    memset(s->rx, 0, sizeof(s->rx));
    uint32_t count = NOVA_RGB_FRAME_BYTES + ((read_reg(s, 0x40005010) & 8u) ? 1u : 0u);
    write_reg(s, 0x40005028, count);
    write_reg(s, 0x4000502c, (uint32_t)(uintptr_t)s->tx);
    write_reg(s, 0x40005028, count);
    write_reg(s, 0x40005030, (uint32_t)(uintptr_t)s->rx);
    acknowledge(s);
    write_reg(s, 0x40005010, read_reg(s, 0x40005010) | 0x60u);
    s->started = s->io.ticks();
    s->active  = true;
    ++s->submitted;
    write_reg(s, 0x40005000, 1);
    return true;
}
