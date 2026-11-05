// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "host.h"
#include "quantum.h"
#include "usb_device_state.h"
#include "ranked_usb_device.h"
#include "../recovered_clock.h"
#ifdef NOVA_USB_DIAGNOSTIC
#    include "usb_diagnostic.h"
#endif
#ifdef RAW_ENABLE
#    include "raw_hid.h"
enum { NOVA_RAW_BYTES = 32, NOVA_RAW_QUEUE = 4 };
static uint8_t          raw_rx[NOVA_RAW_QUEUE][NOVA_RAW_BYTES], raw_tx[NOVA_RAW_BYTES], raw_control_out[NOVA_RAW_BYTES];
static volatile uint8_t raw_rx_head, raw_rx_tail;
static volatile bool    raw_tx_pending;
volatile uint32_t       nova_via_rx_rejected, nova_via_tx_rejected;
static void             raw_packet(void *context, unsigned endpoint, const uint8_t *data, uint16_t length) {
    (void)context;
    if (endpoint != 3 || length != NOVA_RAW_BYTES || !data) {
        ++nova_via_rx_rejected;
        return;
    }
    uint8_t next = (uint8_t)((raw_rx_head + 1u) % NOVA_RAW_QUEUE);
    if (next == raw_rx_tail) {
        ++nova_via_rx_rejected;
        return;
    }
    memcpy(raw_rx[raw_rx_head], data, NOVA_RAW_BYTES);
    raw_rx_head = next;
}
static void send_raw(uint8_t *data, uint8_t length) {
    if (length != NOVA_RAW_BYTES || raw_tx_pending) {
        ++nova_via_tx_rejected;
        return;
    }
    memcpy(raw_tx, data, NOVA_RAW_BYTES);
    raw_tx_pending = true;
}
#endif

#define REG32(a) (*(volatile uint32_t *)(uintptr_t)(a))
extern void              nova_platform_delay_original_units(uint32_t);
extern int               nova_platform_delay_original_long(uint32_t);
static ranked_usb_device device;
static volatile bool     power_pending;
static bool              power_applied;
static volatile bool     protocol_pending;
static uint32_t          suspended_at, last_wake_scan;
static report_keyboard_t latest_report;
static volatile bool     report_pending;
static uint8_t           keyboard_leds, idle_rate, protocol = 1, led_out;
#ifdef NKRO_ENABLE
static report_nkro_t latest_nkro = {.report_id = REPORT_ID_NKRO};
static volatile bool nkro_pending;
static uint8_t       nkro_idle, nkro_led_out[2];
#    ifdef RAW_ENABLE
#        define NKRO_INTERFACE 2
#    else
#        define NKRO_INTERFACE 1
#    endif
#    define NKRO_CONFIGURATION 9, 4, NKRO_INTERFACE, 0, 1, 3, 0, 0, 0, 9, 0x21, 0x11, 0x01, 0, 1, 0x22, sizeof(nkro_hid_report), 0, 7, 5, 0x84, 3, sizeof(report_nkro_t), 0, 1,
#    define NKRO_CONFIGURATION_SIZE 25
#    define NKRO_INTERFACE_COUNT 1
static const uint8_t nkro_hid_report[] = {0x05, 0x01, 0x09, 0x06, 0xa1, 0x01, 0x85, REPORT_ID_NKRO, 0x05, 0x07, 0x19, 0xe0, 0x29, 0xe7, 0x15, 0, 0x25, 1, 0x95, 8, 0x75, 1, 0x81, 2, 0x19, 0, 0x29, NKRO_REPORT_BITS * 8 - 1, 0x95, NKRO_REPORT_BITS * 8, 0x75, 1, 0x81, 2, 0x05, 8, 0x19, 1, 0x29, 5, 0x95, 5, 0x75, 1, 0x91, 2, 0x95, 1, 0x75, 3, 0x91, 1, 0xc0};
_Static_assert(sizeof(report_nkro_t) == 32, "NKRO descriptor requires a 32-byte report");
#else
#    define NKRO_CONFIGURATION
#    define NKRO_CONFIGURATION_SIZE 0
#    define NKRO_INTERFACE_COUNT 0
#endif

/* Boot keyboard plus optional NKRO and Raw HID interfaces describe this runtime,
 * not the original vendor's multi-interface firmware. No assigned new PID.
 */
static const uint8_t hid_report[]        = {0x05, 0x01, 0x09, 0x06, 0xa1, 0x01, 0x05, 0x07, 0x19, 0xe0, 0x29, 0xe7, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x08, 0x81, 0x02, 0x95, 0x01, 0x75, 0x08, 0x81, 0x01, 0x95, 0x05, 0x75, 0x01, 0x05, 0x08, 0x19, 0x01, 0x29, 0x05, 0x91, 0x02, 0x95, 0x01, 0x75, 0x03, 0x91, 0x01, 0x95, 0x06, 0x75, 0x08, 0x15, 0x00, 0x25, 0x73, 0x05, 0x07, 0x19, 0x00, 0x29, 0x73, 0x81, 0x00, 0xc0};
static const uint8_t device_descriptor[] = {18, 1, 0x10, 0x01, 0, 0, 0, 8, VENDOR_ID & 255, VENDOR_ID >> 8, PRODUCT_ID & 255, PRODUCT_ID >> 8, DEVICE_VER & 255, DEVICE_VER >> 8, 1, 2, 0, 1};
#ifdef RAW_ENABLE
static const uint8_t raw_report[]    = {0x06, 0x60, 0xff, 0x09, 0x61, 0xa1, 0x01, 0x09, 0x62, 0x15, 0x00, 0x26, 0xff, 0x00, 0x75, 0x08, 0x95, 32, 0x81, 0x02, 0x09, 0x63, 0x95, 32, 0x91, 0x02, 0xc0};
static const uint8_t configuration[] = {9, 2, 66 + NKRO_CONFIGURATION_SIZE, 0, 2 + NKRO_INTERFACE_COUNT, 1, 0, 0xa0, 50, 9, 4, 0, 0, 1, 3, 1, 1, 0, 9, 0x21, 0x11, 0x01, 0, 1, 0x22, sizeof(hid_report), 0, 7, 5, 0x81, 3, 8, 0, 1, 9, 4, 1, 0, 2, 3, 0, 0, 0, 9, 0x21, 0x11, 0x01, 0, 1, 0x22, sizeof(raw_report), 0, 7, 5, 0x82, 3, 32, 0, 1, 7, 5, 0x03, 3, 32, 0, 1, NKRO_CONFIGURATION};
#else
static const uint8_t configuration[] = {9, 2, 34 + NKRO_CONFIGURATION_SIZE, 0, 1 + NKRO_INTERFACE_COUNT, 1, 0, 0xa0, 50, 9, 4, 0, 0, 1, 3, 1, 1, 0, 9, 0x21, 0x11, 0x01, 0, 1, 0x22, sizeof(hid_report), 0, 7, 5, 0x81, 3, 8, 0, 1, NKRO_CONFIGURATION};
#endif
static const uint8_t language[] = {4, 3, 9, 4};

#define USB_STRING(name, value)                                    \
    static const struct __attribute__((packed)) {                  \
        uint8_t  length;                                           \
        uint8_t  type;                                             \
        uint16_t text[(sizeof(u"" value) / sizeof(uint16_t)) - 1]; \
    } name = {sizeof(u"" value), 3, u"" value};                    \
    _Static_assert(sizeof(name) <= 255, "USB string descriptor exceeds one-byte length")

USB_STRING(manufacturer_string, MANUFACTURER);
USB_STRING(product_string, PRODUCT);

static const uint8_t *descriptor(void *context, uint8_t type, uint8_t index, uint16_t interface_number, uint16_t *length) {
    (void)context;
    if (type == 1 && index == 0) {
        *length = sizeof(device_descriptor);
        return device_descriptor;
    }
    if (type == 2 && index == 0) {
        *length = sizeof(configuration);
        return configuration;
    }
    if (type == 3 && index == 0) {
        *length = sizeof(language);
        return language;
    }
    if (type == 3 && index == 1) {
        *length = sizeof(manufacturer_string);
        return (const uint8_t *)&manufacturer_string;
    }
    if (type == 3 && index == 2) {
        *length = sizeof(product_string);
        return (const uint8_t *)&product_string;
    }
#ifdef NKRO_ENABLE
    if (interface_number == NKRO_INTERFACE && index == 0) {
        if (type == 0x21) {
            *length = 9;
            return configuration + sizeof(configuration) - NKRO_CONFIGURATION_SIZE + 9;
        }
        if (type == 0x22) {
            *length = sizeof(nkro_hid_report);
            return nkro_hid_report;
        }
    }
#endif
#ifdef RAW_ENABLE
    if (interface_number == 1 && index == 0) {
        if (type == 0x21) {
            *length = 9;
            return configuration + 43;
        }
        if (type == 0x22) {
            *length = sizeof(raw_report);
            return raw_report;
        }
    }
#endif
    if (interface_number == 0 && index == 0) {
        if (type == 0x21) {
            *length = 9;
            return configuration + 18;
        }
        if (type == 0x22) {
            *length = sizeof(hid_report);
            return hid_report;
        }
    }
    *length = 0;
    return 0;
}
static void configured(void *context, uint8_t value) {
    (void)context;
#ifdef NOVA_USB_DIAGNOSTIC
    nova_usb_diagnostic_configured(value);
#endif
    usb_device_state_set_configuration(value != 0, value);
    if (!value) {
        protocol         = 1;
        idle_rate        = 0;
        protocol_pending = true;
    }
    power_pending  = true;
    report_pending = true;
#ifdef NKRO_ENABLE
    memset(&latest_nkro, 0, sizeof(latest_nkro));
    latest_nkro.report_id = REPORT_ID_NKRO;
    nkro_pending          = true;
    nkro_idle             = 0;
#endif
#ifdef RAW_ENABLE
    raw_rx_head    = 0;
    raw_rx_tail    = 0;
    raw_tx_pending = false;
#endif
}
static void power_changed(void *context, bool suspended) {
    (void)context;
    if (suspended) suspended_at = last_wake_scan = timer_read32();
    /* IRQ context only records work; QMK hooks run in the main loop. */
    power_pending = true;
}
bool nova_usb_keyboard_suspended(void) {
    return device.suspended || power_pending;
}
void nova_usb_keyboard_pre_task(void) {
    uint32_t primask;
    __asm__ volatile("mrs %0, primask\ncpsid i" : "=r"(primask)::"memory");
    bool    pending            = power_pending;
    bool    reset_protocol     = protocol_pending;
    uint8_t requested_protocol = protocol;
    bool    suspended          = device.suspended;
    uint8_t configuration      = device.configuration;
    power_pending              = false;
    protocol_pending           = false;
    __asm__ volatile("msr primask, %0" ::"r"(primask) : "memory");
    if (reset_protocol) {
        /* Clear the old and new QMK report formats in main context. This also
         * prevents a held-key bitmap surviving a host protocol change. */
        clear_keyboard();
        usb_device_state_set_protocol((usb_hid_protocol_t)requested_protocol);
        clear_keyboard();
    }
    if (!pending || suspended == power_applied) return;
    power_applied = suspended;
    if (suspended) {
        usb_device_state_set_suspend(configuration != 0, configuration);
        suspend_power_down_quantum();
    } else {
        usb_device_state_set_resume(configuration != 0, configuration);
        suspend_wakeup_init_quantum();
        clear_keyboard();
        if (device.wakeup_requested) update_matrix_state_after_wakeup();
    }
}
void nova_usb_keyboard_suspend_task(void) {
    uint32_t now = timer_read32();
    if (!device.suspended || !device.remote_wakeup || device.wakeup_requested || now - last_wake_scan < 20) return;
    last_wake_scan = now;
    if (!suspend_wakeup_condition()) return;
    uint32_t primask;
    __asm__ volatile("mrs %0, primask" : "=r"(primask));
    if (primask) return;
    /* Serialize the native PHY sequence against USB IRQ4 while SysTick stays
     * running for the bounded pulse. Original f310 also runs it inside USB IRQ. */
    uint32_t enabled   = REG32(0xe000e100u) & (1u << 4);
    REG32(0xe000e180u) = 1u << 4;
    __asm__ volatile("dsb\nisb" ::: "memory");
    ranked_usb_device_remote_wakeup(&device, now - suspended_at);
    if (enabled) REG32(0xe000e100u) = 1u << 4;
}
static bool control(void *context, const ranked_usb_setup *setup, ranked_usb_control_reply *reply) {
    (void)context;
#ifdef NKRO_ENABLE
    if (setup->index == NKRO_INTERFACE) {
        if (setup->request_type == 0x21) {
            if (setup->request == 9 && setup->value == (0x0200 | REPORT_ID_NKRO) && setup->length == 2) {
                reply->out_data     = nkro_led_out;
                reply->out_capacity = sizeof(nkro_led_out);
                return true;
            }
            if (setup->request == 0x0a && setup->length == 0 && ((setup->value & 255) == 0 || (setup->value & 255) == REPORT_ID_NKRO)) {
                nkro_idle = setup->value >> 8;
                return true;
            }
        } else if (setup->request_type == 0xa1) {
            if (setup->request == 1 && setup->value == (0x0100 | REPORT_ID_NKRO)) {
                reply->data   = (const uint8_t *)&latest_nkro;
                reply->length = sizeof(latest_nkro);
                return true;
            }
            if (setup->request == 2 && setup->value == REPORT_ID_NKRO && setup->length == 1) {
                reply->data   = &nkro_idle;
                reply->length = 1;
                return true;
            }
        }
        /* This non-boot interface does not implement SET/GET_PROTOCOL. */
        return false;
    }
#endif
#ifdef RAW_ENABLE
    if (setup->index == 1 && setup->request_type == 0x21 && setup->request == 9 && setup->value == 0x0200 && setup->length == NOVA_RAW_BYTES) {
        reply->out_data     = raw_control_out;
        reply->out_capacity = NOVA_RAW_BYTES;
        return true;
    }
#endif
    if (setup->index != 0) return false;
    if (setup->request_type == 0x21) {
        if (setup->request == 0x09 && setup->value == 0x0200 && setup->length == 1) {
            reply->out_data     = &led_out;
            reply->out_capacity = 1;
            return true;
        }
        if (setup->request == 0x0a && setup->length == 0 && (setup->value & 0xff) == 0) {
            idle_rate = (uint8_t)(setup->value >> 8);
            usb_device_state_set_idle_rate(idle_rate);
            return true;
        }
        if (setup->request == 0x0b && setup->length == 0 && setup->value <= 1) {
            protocol = (uint8_t)setup->value;
            memset(&latest_report, 0, sizeof(latest_report));
            report_pending = true;
#ifdef NKRO_ENABLE
            memset(&latest_nkro, 0, sizeof(latest_nkro));
            latest_nkro.report_id = REPORT_ID_NKRO;
            nkro_pending          = true;
#endif
            protocol_pending = true;
            return true;
        }
    } else if (setup->request_type == 0xa1) {
        if (setup->request == 0x02 && setup->value == 0 && setup->length == 1) {
            reply->data   = &idle_rate;
            reply->length = 1;
            return true;
        }
        if (setup->request == 0x03 && setup->value == 0 && setup->length == 1) {
            reply->data   = &protocol;
            reply->length = 1;
            return true;
        }
        if (setup->request == 0x01 && setup->value == 0x0100) {
            reply->data   = (const uint8_t *)&latest_report;
            reply->length = sizeof(latest_report);
            return true;
        }
    }
    return false;
}
static void control_complete(void *context, const ranked_usb_setup *setup, const uint8_t *data, uint16_t length) {
    (void)context;
#ifdef NKRO_ENABLE
    if (setup->index == NKRO_INTERFACE && setup->request_type == 0x21 && setup->request == 9 && length == 2 && data && data[0] == REPORT_ID_NKRO) {
        keyboard_leds = data[1];
        usb_device_state_set_leds(keyboard_leds);
        return;
    }
#endif
#ifdef RAW_ENABLE
    if (setup->index == 1 && setup->request_type == 0x21 && setup->request == 9) {
        raw_packet(0, 3, data, length);
        return;
    }
#endif
    if (setup->request_type == 0x21 && setup->request == 9 && length == 1 && data) {
        keyboard_leds = data[0];
        usb_device_state_set_leds(keyboard_leds);
    }
}
static uint8_t read8(void *context, uintptr_t address) {
    (void)context;
    return *(volatile uint8_t *)address;
}
static uint32_t read32(void *context, uintptr_t address) {
    (void)context;
    uint32_t value = REG32(address);
#ifdef NOVA_USB_DIAGNOSTIC
    /* Record existing bus observations; never add a controller read. */
    if (address == 0x40016008u)
        nova_usb_diagnostic_status(value);
    else if (address == 0x40016000u)
        nova_usb_diagnostic_event(value & 31u);
    else if (address == 0x40017f58u)
        nova_usb_diagnostic_aux(value);
#endif
    return value;
}
static void write32(void *context, uintptr_t address, uint32_t value) {
    (void)context;
    REG32(address) = value;
}
/* Native controller reset/pull-up helpers0xeea8/0xeed4 call long0xdd80.
 * Clock-gate settling separately uses short0xdde8 below. Preserve that split. */
static void delay_controller_long(void *context, uint32_t value) {
    (void)context;
    (void)nova_platform_delay_original_long(value);
}
static void delay_controller_short(void *context, uint32_t value) {
    (void)context;
    nova_platform_delay_original_units(value);
}
static void delay_controller_ms(void *context, uint32_t value) {
    (void)context;
    wait_ms(value);
}
static uint8_t leds(void) {
    return keyboard_leds;
}
static void send_keyboard(report_keyboard_t *report) {
    /* Main-loop producer; USB ISR consumes only while interrupts are masked. */
    uint32_t primask;
    __asm__ volatile("mrs %0, primask\ncpsid i" : "=r"(primask)::"memory");
    latest_report  = *report;
    report_pending = true;
    __asm__ volatile("msr primask, %0" ::"r"(primask) : "memory");
}
#ifdef NKRO_ENABLE
static void send_nkro(report_nkro_t *report) {
    uint32_t primask;
    __asm__ volatile("mrs %0, primask\ncpsid i" : "=r"(primask)::"memory");
    latest_nkro  = *report;
    nkro_pending = true;
    __asm__ volatile("msr primask, %0" ::"r"(primask) : "memory");
}
#endif
static host_driver_t driver = {
    .keyboard_leds = leds,
    .send_keyboard = send_keyboard,
#ifdef NKRO_ENABLE
    .send_nkro = send_nkro,
#endif
#ifdef RAW_ENABLE
    .send_raw_hid = send_raw,
#endif
};
_Static_assert(sizeof(report_keyboard_t) == 8, "Boot descriptor requires an eight-byte QMK report");

bool nova_usb_keyboard_init(void) {
    nova_original_domain_select(2);
    if (!nova_original_gate_write(0x80000000u, true, nova_platform_delay_original_units)) return false;
    unsigned limit = 100000;
    while ((REG32(0x40014120u) & 1u) == 0 && --limit) {
    }
    if (!limit || !nova_platform_delay_original_long(10)) return false;
    const ranked_usb_bus       bus       = {.read8 = read8, .read32 = read32, .write32 = write32, .delay_original_units = delay_controller_long, .delay_ms = delay_controller_ms, .delay_original_short = delay_controller_short};
    const ranked_usb_callbacks callbacks = {
        .descriptor       = descriptor,
        .configured       = configured,
        .control          = control,
        .control_complete = control_complete,
        .power            = power_changed,
#ifdef RAW_ENABLE
        .packet = raw_packet,
#endif
    };
    usb_device_state_init();
    ranked_usb_device_init(&device, &bus, &callbacks);
    host_set_driver(&driver);
    /* Original priority helper 0x2ba8 encodes two implemented priority bits. */
    REG32(0xe000e404u) = (REG32(0xe000e404u) & ~0xffu) | 0x40u; /* IRQ4 priority1 */
    REG32(0xe000e280u) = 1u << 4;
    REG32(0xe000e100u) = 1u << 4;
    return true;
}
void Vector50(void) {
#ifdef NOVA_USB_DIAGNOSTIC
    nova_usb_diagnostic_irq(true);
#endif
    ranked_usb_device_irq(&device);
#ifdef NOVA_USB_DIAGNOSTIC
    nova_usb_diagnostic_irq(false);
#endif
}
void nova_usb_keyboard_task(void) {
    if (nova_usb_keyboard_suspended()) return;
    static uint32_t last_sent;
#ifdef NKRO_ENABLE
    static uint32_t last_nkro_sent;
#endif
    extern uint32_t timer_read32(void);
    uint32_t        now = timer_read32();
    uint32_t        primask;
    __asm__ volatile("mrs %0, primask\ncpsid i" : "=r"(primask)::"memory");
    if (ranked_usb_device_configured(&device) && (report_pending || (idle_rate && now - last_sent >= (uint32_t)idle_rate * 4))) {
        if (ranked_usb_device_send(&device, 1, (const uint8_t *)&latest_report, sizeof(latest_report))) {
            report_pending = false;
            last_sent      = now;
        }
    }
#ifdef RAW_ENABLE
    if (raw_tx_pending && ranked_usb_device_configured(&device) && ranked_usb_device_send(&device, 2, raw_tx, NOVA_RAW_BYTES)) raw_tx_pending = false;
#endif
#ifdef NKRO_ENABLE
    if (ranked_usb_device_configured(&device) && (nkro_pending || (nkro_idle && now - last_nkro_sent >= (uint32_t)nkro_idle * 4))) {
        if (ranked_usb_device_send(&device, 4, (const uint8_t *)&latest_nkro, sizeof(latest_nkro))) {
            nkro_pending   = false;
            last_nkro_sent = now;
        }
    }
#endif
    __asm__ volatile("msr primask, %0" ::"r"(primask) : "memory");
}

#ifdef RAW_ENABLE
void raw_hid_task(void) {
    if (nova_usb_keyboard_suspended()) return;
    /* Parse VIA outside the USB ISR. Only process another request once its
     * predecessor's response was submitted; bounded RX ring owns packet data. */
    uint8_t  command[NOVA_RAW_BYTES];
    bool     have_command = false;
    uint32_t primask;
    __asm__ volatile("mrs %0, primask\ncpsid i" : "=r"(primask)::"memory");
    if (!raw_tx_pending && raw_rx_tail != raw_rx_head) {
        memcpy(command, raw_rx[raw_rx_tail], NOVA_RAW_BYTES);
        raw_rx_tail  = (uint8_t)((raw_rx_tail + 1u) % NOVA_RAW_QUEUE);
        have_command = true;
    }
    __asm__ volatile("msr primask, %0" ::"r"(primask) : "memory");
    if (have_command) raw_hid_receive(command, NOVA_RAW_BYTES);
}
#endif
