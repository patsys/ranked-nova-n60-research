#ifndef RANKED_USB_DEVICE_H
#define RANKED_USB_DEVICE_H
#include "ranked_usb_io.h"

typedef struct {
    void *context;
    uint8_t (*read8)(void *, uintptr_t);
    uint32_t (*read32)(void *, uintptr_t);
    void (*write32)(void *, uintptr_t, uint32_t);
    void (*delay_original_units)(void *, uint32_t);
} ranked_usb_bus;
typedef struct {
    const uint8_t *data;
    uint16_t length;
    uint8_t *out_data;
    uint16_t out_capacity;
} ranked_usb_control_reply;
typedef struct {
    void *context;
    const uint8_t *(*descriptor)(void *, uint8_t type, uint8_t index,
                                 uint16_t interface_number, uint16_t *length);
    void (*configured)(void *, uint8_t configuration);
    bool (*control)(void *, const ranked_usb_setup *, ranked_usb_control_reply *);
    void (*control_complete)(void *, const ranked_usb_setup *, const uint8_t *, uint16_t);
    void (*packet)(void *, unsigned endpoint, const uint8_t *, uint16_t);
    void (*frame)(void *);
    void (*event)(void *, unsigned raw_event);
} ranked_usb_callbacks;
typedef enum { RANKED_EP0_IDLE, RANKED_EP0_IN_DATA, RANKED_EP0_OUT_DATA,
               RANKED_EP0_IN_STATUS, RANKED_EP0_OUT_STATUS, RANKED_EP0_STALL } ranked_usb_phase;
typedef struct ranked_usb_device {
    ranked_usb_bus bus;
    ranked_usb_callbacks callbacks;
    ranked_usb_setup setup;
    ranked_usb_control_reply reply;
    ranked_usb_phase phase;
    uint16_t transferred, total;
    uint16_t in_state, out_state;
    uint8_t address, pending_address, configuration;
    uint8_t small_reply[2];
    bool apply_address, need_zlp, remote_wakeup;
    volatile bool ready[6];
} ranked_usb_device;

/* Clock/pin/NVIC setup belongs to the platform. This initializes controller
 * registers using recovered0x46fc ordering after the USB clock is enabled. */
void ranked_usb_device_init(ranked_usb_device *, const ranked_usb_bus *, const ranked_usb_callbacks *);
void ranked_usb_device_irq(ranked_usb_device *);
void ranked_usb_device_aux_irq(ranked_usb_device *);
bool ranked_usb_device_send(ranked_usb_device *, unsigned endpoint, const uint8_t *, size_t);
bool ranked_usb_device_configured(const ranked_usb_device *);
#endif
