#include "ranked_usb_io.h"

bool ranked_usb_fifo_submit(const ranked_usb_io *io, unsigned endpoint,
                            const uint8_t *source, size_t length) {
    if (!io || !io->write32 || endpoint > RANKED_USB_LAST_ENDPOINT ||
        (!source && length) ||
        length > (endpoint == 0 ? RANKED_USB_EP0_PACKET_BYTES :
                                  RANKED_USB_INTERRUPT_PACKET_BYTES)) {
        return false;
    }
    uintptr_t fifo = UINT32_C(0x40017c00) - (uintptr_t)endpoint * 0x200u;
    for (size_t i = 0; i < length; ++i) {
        io->write32(io->context, fifo + i * 4u, source[i]);
    }
    io->write32(io->context, UINT32_C(0x40017ed4) + endpoint * 8u,
                (uint32_t)length);
    return true;
}

bool ranked_usb_ep0_receive(const ranked_usb_io *io, uint8_t *destination,
                           size_t length) {
    if (!io || !io->read8 || (!destination && length) ||
        length > RANKED_USB_EP0_PACKET_BYTES) {
        return false;
    }
    for (size_t i = 0; i < length; ++i) {
        destination[i] = io->read8(io->context,
                                           UINT32_C(0x40017b00) + i * 4u);
    }
    return true;
}

bool ranked_usb_vendor_receive(const ranked_usb_io *io, uint8_t *destination,
                              size_t length) {
    if (!io || !io->read8 || (!destination && length) ||
        length > RANKED_USB_INTERRUPT_PACKET_BYTES) {
        return false;
    }
    for (size_t i = 0; i < length; ++i) {
        destination[i] = io->read8(io->context,
                                           UINT32_C(0x40017500) + i * 4u);
    }
    return true;
}

static uint16_t little16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

bool ranked_usb_read_setup(const ranked_usb_io *io, ranked_usb_setup *setup) {
    if (!io || !io->read8 || !setup) {
        return false;
    }
    uint8_t packet[8];
    for (size_t i = 0; i < sizeof packet; ++i) {
        packet[i] = io->read8(io->context,
                                      UINT32_C(0x40017fa0) + i * 4u);
    }
    setup->request_type = packet[0];
    setup->request = packet[1];
    setup->value = little16(packet + 2);
    setup->index = little16(packet + 4);
    setup->length = little16(packet + 6);
    return true;
}
