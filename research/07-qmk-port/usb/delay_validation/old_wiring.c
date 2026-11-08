#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "host.h"
#include "usb_device_state.h"
#include "ranked_usb_device.h"
#include "../platform/recovered_clock.h"
#ifdef VIA_ENABLE
#include "raw_hid.h"
enum { NOVA_RAW_BYTES=32, NOVA_RAW_QUEUE=4 };
static uint8_t raw_rx[NOVA_RAW_QUEUE][NOVA_RAW_BYTES], raw_tx[NOVA_RAW_BYTES], raw_control_out[NOVA_RAW_BYTES];
static volatile uint8_t raw_rx_head, raw_rx_tail;
static volatile bool raw_tx_pending;
volatile uint32_t nova_via_rx_rejected, nova_via_tx_rejected;
static void raw_packet(void *context, unsigned endpoint, const uint8_t *data, uint16_t length) {
    (void)context;
    if (endpoint != 3 || length != NOVA_RAW_BYTES || !data) { ++nova_via_rx_rejected; return; }
    uint8_t next=(uint8_t)((raw_rx_head+1u)%NOVA_RAW_QUEUE);
    if (next==raw_rx_tail) { ++nova_via_rx_rejected; return; }
    memcpy(raw_rx[raw_rx_head],data,NOVA_RAW_BYTES);
    raw_rx_head=next;
}
static void send_raw(uint8_t *data, uint8_t length) {
    if (length != NOVA_RAW_BYTES || raw_tx_pending) { ++nova_via_tx_rejected; return; }
    memcpy(raw_tx,data,NOVA_RAW_BYTES); raw_tx_pending=true;
}
#endif

#define REG32(a) (*(volatile uint32_t *)(uintptr_t)(a))
extern void nova_platform_delay_original_units(uint32_t);
extern int nova_platform_delay_original_long(uint32_t);
static ranked_usb_device device;
static report_keyboard_t latest_report;
static volatile bool report_pending;
static uint8_t keyboard_leds, idle_rate, protocol = 1, led_out;

/* Single boot-keyboard interface. These descriptors describe THIS runtime,
 * not the original vendor's multi-interface firmware. No assigned new PID.
 */
static const uint8_t hid_report[] = {
    0x05,0x01,0x09,0x06,0xa1,0x01,0x05,0x07,0x19,0xe0,0x29,0xe7,
    0x15,0x00,0x25,0x01,0x75,0x01,0x95,0x08,0x81,0x02,
    0x95,0x01,0x75,0x08,0x81,0x01,
    0x95,0x05,0x75,0x01,0x05,0x08,0x19,0x01,0x29,0x05,0x91,0x02,
    0x95,0x01,0x75,0x03,0x91,0x01,
    0x95,0x06,0x75,0x08,0x15,0x00,0x25,0x73,0x05,0x07,0x19,0x00,
    0x29,0x73,0x81,0x00,0xc0
};
static const uint8_t device_descriptor[] = {
    18,1,0x10,0x01,0,0,0,8,0x32,0x35,0xa3,0xa0,0,0,0,0,0,1
};
#ifdef VIA_ENABLE
static const uint8_t raw_report[] = {
    0x06,0x60,0xff,0x09,0x61,0xa1,0x01,0x09,0x62,
    0x15,0x00,0x26,0xff,0x00,0x75,0x08,0x95,32,0x81,0x02,
    0x09,0x63,0x95,32,0x91,0x02,0xc0
};
static const uint8_t configuration[] = {
    9,2,66,0,2,1,0,0x80,50,
    9,4,0,0,1,3,1,1,0,
    9,0x21,0x11,0x01,0,1,0x22,sizeof(hid_report),0,
    7,5,0x81,3,8,0,1,
    9,4,1,0,2,3,0,0,0,
    9,0x21,0x11,0x01,0,1,0x22,sizeof(raw_report),0,
    7,5,0x82,3,32,0,1,
    7,5,0x03,3,32,0,1
};
#else
static const uint8_t configuration[] = {
    9,2,34,0,1,1,0,0x80,50,
    9,4,0,0,1,3,1,1,0,
    9,0x21,0x11,0x01,0,1,0x22,sizeof(hid_report),0,
    7,5,0x81,3,8,0,1
};
#endif
static const uint8_t language[] = {4,3,9,4};

static const uint8_t *descriptor(void *context, uint8_t type, uint8_t index,
                                  uint16_t interface_number, uint16_t *length) {
    (void)context;
    if (type == 1 && index == 0) { *length=sizeof(device_descriptor); return device_descriptor; }
    if (type == 2 && index == 0) { *length=sizeof(configuration); return configuration; }
    if (type == 3 && index == 0) { *length=sizeof(language); return language; }
#ifdef VIA_ENABLE
    if (interface_number == 1 && index == 0) {
        if (type == 0x21) { *length=9; return configuration+43; }
        if (type == 0x22) { *length=sizeof(raw_report); return raw_report; }
    }
#endif
    if (interface_number == 0 && index == 0) {
        if (type == 0x21) { *length=9; return configuration+18; }
        if (type == 0x22) { *length=sizeof(hid_report); return hid_report; }
    }
    *length=0; return 0;
}
static void configured(void *context, uint8_t value) {
    (void)context;
    usb_device_state_set_configuration(value != 0, value);
    report_pending = true;
#ifdef VIA_ENABLE
    raw_rx_head=0; raw_rx_tail=0; raw_tx_pending=false;
#endif
}
static bool control(void *context, const ranked_usb_setup *setup, ranked_usb_control_reply *reply) {
    (void)context;
#ifdef VIA_ENABLE
    if (setup->index==1 && setup->request_type==0x21 && setup->request==9 &&
        setup->value==0x0200 && setup->length==NOVA_RAW_BYTES) {
        reply->out_data=raw_control_out; reply->out_capacity=NOVA_RAW_BYTES; return true;
    }
#endif
    if (setup->index != 0) return false;
    if (setup->request_type == 0x21) {
        if (setup->request == 0x09 && setup->value == 0x0200 && setup->length == 1) {
            reply->out_data=&led_out; reply->out_capacity=1; return true;
        }
        if (setup->request == 0x0a && setup->length == 0 && (setup->value & 0xff) == 0) {
            idle_rate=(uint8_t)(setup->value >> 8); usb_device_state_set_idle_rate(idle_rate); return true;
        }
        if (setup->request == 0x0b && setup->length == 0 && setup->value <= 1) {
            protocol=(uint8_t)setup->value; usb_device_state_set_protocol((usb_hid_protocol_t)protocol); return true;
        }
    } else if (setup->request_type == 0xa1) {
        if (setup->request == 0x02 && setup->value == 0 && setup->length == 1) {
            reply->data=&idle_rate; reply->length=1; return true;
        }
        if (setup->request == 0x03 && setup->value == 0 && setup->length == 1) {
            reply->data=&protocol; reply->length=1; return true;
        }
        if (setup->request == 0x01 && setup->value == 0x0100) {
            reply->data=(const uint8_t *)&latest_report; reply->length=sizeof(latest_report); return true;
        }
    }
    return false;
}
static void control_complete(void *context, const ranked_usb_setup *setup, const uint8_t *data, uint16_t length) {
    (void)context;
#ifdef VIA_ENABLE
    if (setup->index==1 && setup->request_type==0x21 && setup->request==9) {
        raw_packet(0,3,data,length); return;
    }
#endif
    if (setup->request_type == 0x21 && setup->request == 9 && length == 1 && data) {
        keyboard_leds=data[0]; usb_device_state_set_leds(keyboard_leds);
    }
}
static uint8_t read8(void *context, uintptr_t address) { (void)context; return *(volatile uint8_t *)address; }
static uint32_t read32(void *context, uintptr_t address) { (void)context; return REG32(address); }
static void write32(void *context, uintptr_t address, uint32_t value) { (void)context; REG32(address)=value; }
/* Native controller reset/pull-up helpers0xeea8/0xeed4 call long0xdd80.
 * Clock-gate settling separately uses short0xdde8 below. Preserve that split. */
static void delay_controller_long(void *context, uint32_t value) {
    (void)context;
    nova_platform_delay_original_units(value);
}
static uint8_t leds(void) { return keyboard_leds; }
static void send_keyboard(report_keyboard_t *report) {
    /* Main-loop producer; USB ISR consumes only while interrupts are masked. */
    uint32_t primask;
    __asm__ volatile("mrs %0, primask\ncpsid i" : "=r"(primask) :: "memory");
    latest_report=*report; report_pending=true;
    __asm__ volatile("msr primask, %0" :: "r"(primask) : "memory");
}
static host_driver_t driver = { .keyboard_leds=leds, .send_keyboard=send_keyboard,
#ifdef VIA_ENABLE
    .send_raw_hid=send_raw,
#endif
};
_Static_assert(sizeof(report_keyboard_t)==8, "Boot descriptor requires an eight-byte QMK report");

bool nova_usb_keyboard_init(void) {
    nova_original_domain_select(2);
    if (!nova_original_gate_write(0x80000000u, true, nova_platform_delay_original_units)) return false;
    unsigned limit=100000;
    while ((REG32(0x40014120u)&1u)==0 && --limit) {}
    if (!limit || !nova_platform_delay_original_long(10)) return false;
    const ranked_usb_bus bus={.read8=read8,.read32=read32,.write32=write32,.delay_original_units=delay_controller_long};
    const ranked_usb_callbacks callbacks={.descriptor=descriptor,.configured=configured,.control=control,.control_complete=control_complete,
#ifdef VIA_ENABLE
        .packet=raw_packet,
#endif
    };
    usb_device_state_init();
    ranked_usb_device_init(&device,&bus,&callbacks);
    host_set_driver(&driver);
    /* Original priority helper 0x2ba8 encodes two implemented priority bits. */
    REG32(0xe000e404u)=(REG32(0xe000e404u)&~0xffu)|0x40u; /* IRQ4 priority1 */
    REG32(0xe000e280u)=1u<<4;
    REG32(0xe000e100u)=1u<<4;
    return true;
}
void Vector50(void) { ranked_usb_device_irq(&device); }
void nova_usb_keyboard_task(void) {
    static uint32_t last_sent;
    extern uint32_t timer_read32(void);
    uint32_t now=timer_read32();
    uint32_t primask;
    __asm__ volatile("mrs %0, primask\ncpsid i" : "=r"(primask) :: "memory");
    if (ranked_usb_device_configured(&device) &&
        (report_pending || (idle_rate && now-last_sent >= (uint32_t)idle_rate*4))) {
        if (ranked_usb_device_send(&device,1,(const uint8_t *)&latest_report,sizeof(latest_report))) {
            report_pending=false; last_sent=now;
        }
    }
#ifdef VIA_ENABLE
    if (raw_tx_pending && ranked_usb_device_configured(&device) &&
        ranked_usb_device_send(&device,2,raw_tx,NOVA_RAW_BYTES)) raw_tx_pending=false;
#endif
    __asm__ volatile("msr primask, %0" :: "r"(primask) : "memory");
#ifdef VIA_ENABLE
    /* Parse VIA outside the USB ISR. Only process another request once its
     * predecessor's response was submitted; bounded RX ring owns packet data. */
    uint8_t command[NOVA_RAW_BYTES];
    bool have_command=false;
    __asm__ volatile("mrs %0, primask\ncpsid i" : "=r"(primask) :: "memory");
    if (!raw_tx_pending && raw_rx_tail!=raw_rx_head) {
        memcpy(command,raw_rx[raw_rx_tail],NOVA_RAW_BYTES);
        raw_rx_tail=(uint8_t)((raw_rx_tail+1u)%NOVA_RAW_QUEUE); have_command=true;
    }
    __asm__ volatile("msr primask, %0" :: "r"(primask) : "memory");
    if (have_command) raw_hid_receive(command,NOVA_RAW_BYTES);
#endif
}
