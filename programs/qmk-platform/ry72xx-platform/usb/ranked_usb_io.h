// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

/* Recovered FIFO primitives, not a complete QMK USB backend.
 * Evidence: original application0xf118,0xf3fc,0xd4d4,0xdf90.
 * These functions require caller-owned endpoint readiness/IRQ serialization.
 * No flash writes, native function calls, or device access occur implicitly.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef uint8_t (*ranked_usb_read8_fn)(void *context, uintptr_t address);
typedef void (*ranked_usb_write32_fn)(void *context, uintptr_t address, uint32_t value);
typedef struct {
    void                 *context;
    ranked_usb_read8_fn   read8;
    ranked_usb_write32_fn write32;
} ranked_usb_io;

enum { RANKED_USB_IRQ = 4, RANKED_USB_EP0_PACKET_BYTES = 8, RANKED_USB_INTERRUPT_PACKET_BYTES = 64, RANKED_USB_LAST_ENDPOINT = 5, RANKED_USB_RAW_IN_ENDPOINT = 2, RANKED_USB_RAW_OUT_ENDPOINT = 3, RANKED_USB_RAW_REPORT_BYTES = 32 };

typedef struct {
    uint8_t  request_type;
    uint8_t  request;
    uint16_t value;
    uint16_t index;
    uint16_t length;
} ranked_usb_setup;

/* Submit only when the endpoint is ready. Original FIFO geometry validated
 * offline for ep0..5; EP0 packet size8 is from the original device descriptor.
 * Success means stores were issued, not that a host acknowledged a transfer.
 */
bool ranked_usb_fifo_submit(const ranked_usb_io *io, unsigned endpoint, const uint8_t *source, size_t length);

/* Read one EP0 OUT packet; original0xd4d4 consumes low byte of each FIFO word.
 * Caller must obtain received length and serialize access with the USB ISR.
 */
bool ranked_usb_ep0_receive(const ranked_usb_io *io, uint8_t *destination, size_t length);

/* Proven application vendor OUT endpoint3 FIFO (native0x287c). This reads the
 * supplied packet length; it does not clear the IRQ or invoke command handlers.
 */
bool ranked_usb_vendor_receive(const ranked_usb_io *io, uint8_t *destination, size_t length);

/* Read the eight SETUP bytes from word-spaced setup registers and decode USB
 * little-endian fields. This does not acknowledge the SETUP event.
 */
bool ranked_usb_read_setup(const ranked_usb_io *io, ranked_usb_setup *setup);
