// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "wear_leveling_internal.h"
#include "recovered_clock.h"
#include "nova_flash_guards.h"

/*
 * The stock application maps flash page IDs to 512-byte pages and exposes a
 * 32-bit word-programming command at 0x40013000. Only F8-FF are assigned to
 * this driver. Their erased state and metadata permission bits were checked
 * by a verified read-only full-flash probe; E0-F7 contain preserved data.
 */
#define NOVA_FLASH_CONTROLLER 0x40013000u
#define NOVA_FLASH_METADATA 0x10000600u
#define NOVA_FLASH_PAGE_SIZE 512u
#define NOVA_FLASH_FIRST_PAGE 0xF8u
#define NOVA_FLASH_LAST_PAGE 0xFFu
#define NOVA_FLASH_PAGE_COUNT (NOVA_FLASH_LAST_PAGE - NOVA_FLASH_FIRST_PAGE + 1u)
#define NOVA_FLASH_BASE_ADDRESS (NOVA_FLASH_FIRST_PAGE * NOVA_FLASH_PAGE_SIZE)
#define NOVA_FLASH_BYTES (NOVA_FLASH_PAGE_COUNT * NOVA_FLASH_PAGE_SIZE)
#define NOVA_FLASH_TIMEOUT (1u << 20)
#define NOVA_FLASH_PAGE_GATE_OFFSET 0xD0u

STATIC_ASSERT(WEAR_LEVELING_BACKING_SIZE == NOVA_FLASH_BYTES, "Wear-leveling size must be exactly pages F8-FF");
STATIC_ASSERT(BACKING_STORE_WRITE_SIZE == 4, "Nova flash programming uses 32-bit words");
STATIC_ASSERT(sizeof(backing_store_int_t) == NOVA_FLASH_WRITE_BYTES, "Nova backing store entries must be 32 bits");
STATIC_ASSERT(NOVA_FLASH_BYTES == NOVA_FLASH_BACKING_BYTES, "Nova flash guard range must match F8-FF");

static volatile uint32_t *const flash_registers = (volatile uint32_t *)NOVA_FLASH_CONTROLLER;
static bool controller_ready;
static bool write_unlocked;

#ifdef NOVA_USB_DIAGNOSTIC
/* Temporary Raw HID diagnostics for the persistence investigation. */
static volatile struct {
    uint32_t stage;
    uint32_t address;
    uint32_t page;
    uint32_t permission;
    uint32_t gate;
    uint32_t controller_status;
    uint32_t flash_word;
} flash_diagnostic;

void nova_flash_diagnostic(uint8_t *data) {
    data[0] = (uint8_t)flash_diagnostic.stage;
    const uint32_t flags = (controller_ready ? 1u : 0u) | (write_unlocked ? 2u : 0u);
    for (unsigned i = 0; i < 4; ++i) data[1 + i] = (uint8_t)(flags >> (8u * i));
    const uint32_t values[] = {flash_diagnostic.address, flash_diagnostic.page,
                               flash_diagnostic.permission, flash_diagnostic.gate,
                               flash_diagnostic.controller_status, flash_diagnostic.flash_word};
    for (unsigned j = 0; j < sizeof(values) / sizeof(values[0]); ++j) {
        for (unsigned i = 0; i < 4; ++i) data[5 + 4 * j + i] = (uint8_t)(values[j] >> (8u * i));
    }
}
#endif

static uint32_t irq_disable(void) {
    uint32_t primask;
    __asm__ volatile("mrs %0, primask\n\tcpsid i" : "=r"(primask) : : "memory");
    return primask;
}

static void irq_restore(uint32_t primask) {
    if ((primask & 1u) == 0) {
        __asm__ volatile("cpsie i" : : : "memory");
    }
}

static bool flash_configure(void) {
    const uint32_t hz = nova_original_clock_effective_hz();
    if (hz < 1500000u || hz > 48000000u) {
        return false;
    }

    const uint32_t mhz = hz / 1000000u;
    flash_registers[0x14u / 4u] = 0x207u;
    flash_registers[0x18u / 4u] = 0x0Bu;
    flash_registers[0x20u / 4u] = 0x40u;
    flash_registers[0x24u / 4u] = 0x137u;
    flash_registers[0x28u / 4u] = (0x144u * mhz) / 0x30u;
    flash_registers[0x30u / 4u] = 0x104u;
    flash_registers[0x38u / 4u] = 0x114u;
    flash_registers[0x3Cu / 4u] = (0x34BC0u * mhz) / 0x30u;
    flash_registers[0x40u / 4u] = (0x15F900u * mhz) / 0x30u;
    flash_registers[0x4Cu / 4u] = 6u;
    __asm__ volatile("dsb" : : : "memory");
    return true;
}

static bool page_allowed(uint32_t page) {
    if (page < NOVA_FLASH_FIRST_PAGE || page > NOVA_FLASH_LAST_PAGE) {
        return false;
    }
    const uint32_t group = page >> 5;
    const uint32_t bit   = 1u << (page & 31u);
    const volatile uint32_t *const allow = (const volatile uint32_t *)(NOVA_FLASH_METADATA + 0x50u + group * 4u);
    const volatile uint32_t *const gate  = (const volatile uint32_t *)(NOVA_FLASH_CONTROLLER + NOVA_FLASH_PAGE_GATE_OFFSET + group * 4u);
#ifdef NOVA_USB_DIAGNOSTIC
    flash_diagnostic.page       = page;
    flash_diagnostic.permission = *allow;
    flash_diagnostic.gate       = *gate;
#endif
    /* The recovered stub overwrites this write-only/aliasing register with
     * the one-hot gate immediately before a controller operation. On the
     * running Nova the register reads as all ones, so its readback is not a
     * valid precondition. The protected metadata permission bitmap is the
     * authoritative page check here.
     */
    (void)gate;
    return (*allow & bit) != 0u;
}

static bool wait_ready(void) {
    for (uint32_t attempt = 0; attempt < NOVA_FLASH_TIMEOUT; ++attempt) {
        if ((flash_registers[0x10u / 4u] & 2u) == 0u) {
            __asm__ volatile("dsb" : : : "memory");
            return true;
        }
    }
    return false;
}

static bool erase_page(uint32_t page) {
    if (!page_allowed(page)) {
        return false;
    }

    const uint32_t primask = irq_disable();
    volatile uint32_t *const gate = (volatile uint32_t *)(NOVA_FLASH_CONTROLLER + NOVA_FLASH_PAGE_GATE_OFFSET + (page >> 5) * 4u);
    const uint32_t bit = 1u << (page & 31u);
    *gate = bit;
    flash_registers[0x04u / 4u] = page << 7;
    flash_registers[0x00u / 4u] = 2u;
    flash_registers[0x10u / 4u] |= 1u;
    const bool ok = wait_ready();
    /* Match the vendor stub: clear only this page's gate bit. This register
     * aliases a page bitmap, so writing zero can also clear unrelated bits. */
    *gate &= ~bit;
    irq_restore(primask);
    if (!ok) {
        return false;
    }

    const volatile uint32_t *const contents = (const volatile uint32_t *)(page * NOVA_FLASH_PAGE_SIZE);
    for (uint32_t word = 0; word < NOVA_FLASH_PAGE_SIZE / sizeof(uint32_t); ++word) {
        if (contents[word] != UINT32_MAX) {
            return false;
        }
    }
    return true;
}

bool backing_store_init(void) {
    controller_ready = flash_configure();
    write_unlocked  = false;
    return controller_ready;
}

bool backing_store_unlock(void) {
    if (!controller_ready) {
        return false;
    }
    write_unlocked = true;
    return true;
}

bool backing_store_lock(void) {
    write_unlocked = false;
    return true;
}

bool backing_store_erase(void) {
    if (!controller_ready || !write_unlocked) {
        return false;
    }
    for (uint32_t page = NOVA_FLASH_FIRST_PAGE; page <= NOVA_FLASH_LAST_PAGE; ++page) {
        if (!erase_page(page)) {
            return false;
        }
    }
    return true;
}

bool backing_store_write(uint32_t address, backing_store_int_t value) {
#ifdef NOVA_USB_DIAGNOSTIC
    flash_diagnostic.address = address;
    flash_diagnostic.flash_word = UINT32_MAX;
    flash_diagnostic.controller_status = flash_registers[0x10u / 4u];
    flash_diagnostic.stage = 1u;
#endif
    if (!controller_ready) {
#ifdef NOVA_USB_DIAGNOSTIC
        flash_diagnostic.stage = 0x10u;
#endif
        return false;
    }
    if (!write_unlocked) {
#ifdef NOVA_USB_DIAGNOSTIC
        flash_diagnostic.stage = 0x11u;
#endif
        return false;
    }
    if (!nova_flash_address_valid(address)) {
#ifdef NOVA_USB_DIAGNOSTIC
        flash_diagnostic.stage = 0x12u;
#endif
        return false;
    }

    const uint32_t page = NOVA_FLASH_FIRST_PAGE + address / NOVA_FLASH_PAGE_SIZE;
    const uint32_t word = (address % NOVA_FLASH_PAGE_SIZE) / sizeof(value);
    if (!page_allowed(page)) {
#ifdef NOVA_USB_DIAGNOSTIC
        flash_diagnostic.stage = 2u;
#endif
        return false;
    }

    volatile uint32_t *const contents = (volatile uint32_t *)(NOVA_FLASH_BASE_ADDRESS + address);
    /* Refuse non-erased cells; QMK's log appends and only rewrites after erase. */
    if (*contents != UINT32_MAX) {
#ifdef NOVA_USB_DIAGNOSTIC
        flash_diagnostic.flash_word = *contents;
        flash_diagnostic.stage = 3u;
#endif
        return false;
    }

    const uint32_t primask = irq_disable();
    volatile uint32_t *const gate = (volatile uint32_t *)(NOVA_FLASH_CONTROLLER + NOVA_FLASH_PAGE_GATE_OFFSET + (page >> 5) * 4u);
    const uint32_t bit = 1u << (page & 31u);
    *gate = bit;
    flash_registers[0x08u / 4u] = ~value;
    flash_registers[0x04u / 4u] = (page << 7) | word;
    flash_registers[0x00u / 4u] = 1u;
    flash_registers[0x10u / 4u] |= 1u;
    const bool ok = wait_ready();
    /* Keep the recovered stub's bit-preserving gate-clear sequence. */
    *gate &= ~bit;
    irq_restore(primask);
    const bool verified = ok && *contents == ~value;
#ifdef NOVA_USB_DIAGNOSTIC
    flash_diagnostic.controller_status = flash_registers[0x10u / 4u];
    flash_diagnostic.flash_word = *contents;
    flash_diagnostic.stage = !ok ? 4u : (verified ? 5u : 6u);
#endif
    return verified;
}

bool backing_store_read(uint32_t address, backing_store_int_t *value) {
    if (value == NULL || !nova_flash_address_valid(address)) {
        return false;
    }
    const volatile uint32_t *const contents = (const volatile uint32_t *)(NOVA_FLASH_BASE_ADDRESS + address);
    *value = ~*contents;
    return true;
}
