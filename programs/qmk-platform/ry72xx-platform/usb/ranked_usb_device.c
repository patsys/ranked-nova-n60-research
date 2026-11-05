// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#include "ranked_usb_device.h"
#include <string.h>

/* Register operations translated from0xf194/0xf234. Status encodings are kept
 * explicit because IN/OUT EP0 share one register with side-effect bits. */
static uint32_t rd(ranked_usb_device *d, uintptr_t a) {
    return d->bus.read32(d->bus.context, a);
}
static void wr(ranked_usb_device *d, uintptr_t a, uint32_t v) {
    d->bus.write32(d->bus.context, a, v);
}
static void delay(ranked_usb_device *d, uint32_t units) {
    if (d->bus.delay_original_units) d->bus.delay_original_units(d->bus.context, units);
}
static void state(ranked_usb_device *d, unsigned ep, bool in, uint16_t value) {
    if (ep == 0) {
        uint32_t r = rd(d, 0x40017ed0u);
        if (value == (in ? 0x1000 : 0x10))
            r = (r | 1u) & 0x3du;
        else if (value == (in ? 0x2000 : 0x20))
            r = (r | 2u) & 0x2eu;
        else
            r &= 0x2cu;
        wr(d, 0x40017ed0u, r);
    } else {
        uintptr_t a = (in ? 0x40017ed0u : 0x40017f10u) + ep * 8u;
        if (in)
            wr(d, a, value == 0x1000 ? 1u : value == 0x2000 ? 2u : 0u);
        else if (value == 0x10)
            wr(d, a, (d->bus.read8(d->bus.context, a) | 1u) & 3u);
        else if (value == 0x30)
            wr(d, a, 2u);
        else if (value == 0x40)
            wr(d, a + 4, 127u);
    }
}
static ranked_usb_io io(ranked_usb_device *d) {
    ranked_usb_io result = {d->bus.context, d->bus.read8, d->bus.write32};
    return result;
}
static void controller_init(ranked_usb_device *d) {
    /*0x46fc after clock enable0xf0dc. Original delay helper units are not
     * definitively calibrated; the callback receives the original arguments. */
    wr(d, 0x4001401cu, 0x21);
    wr(d, 0x40016000u, 0x80);
    delay(d, 1);
    wr(d, 0x40016000u, 0);
    delay(d, 1);
    wr(d, 0x40017f58u, (rd(d, 0x40017f58u) & 255u) | 8u);
    delay(d, 6);
    wr(d, 0x40017f58u, (rd(d, 0x40017f58u) & 255u) & ~8u);
    wr(d, 0x40016008u, 0);
    wr(d, 0x40016010u, 3);
    wr(d, 0x4001600cu, 3);
    wr(d, 0x40017eb8u, 31);
    wr(d, 0x40017eb0u, 1);
    wr(d, 0x40017ea4u, 63);
    wr(d, 0x40017eb4u, 1);
    wr(d, 0x40017ea8u, 63);
    static const uint8_t cfg[5] = {4, 0x14, 0x24, 0x44, 0x54}, offset[5] = {4, 8, 0x28, 0x30, 0x3c};
    for (unsigned ep = 1; ep < 6; ep++)
        wr(d, 0x40017e00u + ep * 4u, cfg[ep - 1]);
    wr(d, 0x40017e20u, 0x2e);
    for (unsigned ep = 1; ep < 6; ep++)
        wr(d, 0x40017e20u + ep * 4u, offset[ep - 1]);
    wr(d, 0x40017f88u, 0x13);
    wr(d, 0x40017fc0u, 0);
    wr(d, 0x40017fe0u, 8);
    wr(d, 0x40017f8cu, 4);
    wr(d, 0x40017f78u, 1);
    wr(d, 0x40017f7cu, 1);
    wr(d, 0x40017f80u, 0);
    wr(d, 0x40017f84u, 0);
    wr(d, 0x40017f14u, 127);
    d->phase            = RANKED_EP0_IDLE;
    d->in_state         = 0x1000;
    d->out_state        = 0x10;
    d->address          = 0;
    d->pending_address  = 0;
    d->configuration    = 0;
    d->apply_address    = false;
    d->remote_wakeup    = false;
    d->suspended        = false;
    d->wakeup_requested = false;
    d->need_zlp         = false;
    d->transferred      = 0;
    d->total            = 0;
    for (unsigned ep = 0; ep < 6; ep++)
        d->ready[ep] = true;
}
void ranked_usb_device_init(ranked_usb_device *d, const ranked_usb_bus *bus, const ranked_usb_callbacks *callbacks) {
    memset(d, 0, sizeof *d);
    d->bus       = *bus;
    d->callbacks = *callbacks;
    controller_init(d);
}
static void stall(ranked_usb_device *d) {
    d->phase     = RANKED_EP0_STALL;
    d->in_state  = 0x1000;
    d->out_state = 0x10;
}
static void status_in(ranked_usb_device *d) {
    d->phase     = RANKED_EP0_IN_STATUS;
    d->in_state  = 0x3000;
    d->out_state = 0x20;
    wr(d, 0x40017ed4u, 0);
}
static void next_in(ranked_usb_device *d) {
    if (d->transferred < d->total) {
        uint16_t n = d->total - d->transferred;
        if (n > 8) n = 8;
        ranked_usb_io b = io(d);
        ranked_usb_fifo_submit(&b, 0, d->reply.data + d->transferred, n);
        d->transferred += n;
        d->in_state  = 0x3000;
        d->out_state = 0x30;
    } else if (d->need_zlp) {
        d->need_zlp = false;
        wr(d, 0x40017ed4u, 0);
        d->in_state  = 0x3000;
        d->out_state = 0x30;
    } else {
        d->phase     = RANKED_EP0_OUT_STATUS;
        d->in_state  = 0;
        d->out_state = 0x30;
    }
}
static void begin_reply(ranked_usb_device *d) {
    d->transferred = 0;
    if (d->setup.request_type & 0x80) {
        d->total = d->reply.length < d->setup.length ? d->reply.length : d->setup.length;
        if (d->total && !d->reply.data) {
            stall(d);
            return;
        }
        d->need_zlp = d->reply.length < d->setup.length && (d->total % 8u) == 0;
        d->phase    = RANKED_EP0_IN_DATA;
        next_in(d);
    } else if (d->setup.length) {
        if (!d->reply.out_data || d->reply.out_capacity < d->setup.length) {
            stall(d);
            return;
        }
        d->total     = d->setup.length;
        d->phase     = RANKED_EP0_OUT_DATA;
        d->in_state  = 0x2000;
        d->out_state = 0x30;
    } else
        status_in(d);
}
static void setup(ranked_usb_device *d) {
    ranked_usb_io b = io(d);
    ranked_usb_read_setup(&b, &d->setup);
    memset(&d->reply, 0, sizeof d->reply);
    d->apply_address          = false;
    d->need_zlp               = false;
    const ranked_usb_setup *s = &d->setup;
    if ((s->request_type & 0x60u) == 0) {
        if (s->request == 6 && (s->request_type & 0x80) && d->callbacks.descriptor) {
            d->reply.data = d->callbacks.descriptor(d->callbacks.context, s->value >> 8, s->value & 255, s->index, &d->reply.length);
            if (!d->reply.data) {
                stall(d);
                return;
            }
            begin_reply(d);
            return;
        }
        if (s->request == 5 && s->request_type == 0 && s->value < 128 && !s->index && !s->length) {
            d->pending_address = (uint8_t)s->value;
            d->apply_address   = true;
            status_in(d);
            return;
        }
        if (s->request == 9 && s->request_type == 0 && s->value <= 1 && !s->index && !s->length) {
            d->configuration = (uint8_t)s->value;
            d->remote_wakeup = false;
            if (d->callbacks.configured) d->callbacks.configured(d->callbacks.context, d->configuration);
            status_in(d);
            return;
        }
        if (s->request == 8 && s->request_type == 0x80 && !s->value && !s->index && s->length == 1) {
            d->small_reply[0] = d->configuration;
            d->reply.data     = d->small_reply;
            d->reply.length   = 1;
            begin_reply(d);
            return;
        }
        if (s->request == 0 && (s->request_type & 0x80) && !s->value && s->length == 2) {
            d->small_reply[0] = (s->request_type == 0x80 && d->remote_wakeup) ? 2 : 0;
            d->small_reply[1] = 0;
            d->reply.data     = d->small_reply;
            d->reply.length   = 2;
            begin_reply(d);
            return;
        }
        if ((s->request == 1 || s->request == 3) && s->request_type == 0 && s->value == 1 && !s->index && !s->length && d->configuration) {
            d->remote_wakeup = s->request == 3;
            status_in(d);
            return;
        }
        if (s->request == 10 && s->request_type == 0x81 && !s->value && s->length == 1) {
            d->small_reply[0] = 0;
            d->reply.data     = d->small_reply;
            d->reply.length   = 1;
            begin_reply(d);
            return;
        }
        if (s->request == 11 && s->request_type == 1 && !s->value && !s->length) {
            status_in(d);
            return;
        }
    }
    if (d->callbacks.control && d->callbacks.control(d->callbacks.context, s, &d->reply)) {
        begin_reply(d);
        return;
    }
    stall(d);
}
static void in_complete(ranked_usb_device *d) {
    if (d->phase == RANKED_EP0_IN_DATA)
        next_in(d);
    else if (d->phase == RANKED_EP0_IN_STATUS) {
        if (d->apply_address) {
            d->address       = d->pending_address;
            d->apply_address = false;
        }
        /* Original SET_ADDRESS does not issue an address-register store. */
        d->phase     = RANKED_EP0_IDLE;
        d->in_state  = 0x1000;
        d->out_state = 0x10;
        if (d->callbacks.control_complete) d->callbacks.control_complete(d->callbacks.context, &d->setup, d->reply.out_data, d->transferred);
    } else {
        d->in_state  = 0x1000;
        d->out_state = 0x10;
    }
}
static void out_complete(ranked_usb_device *d) {
    if (d->phase == RANKED_EP0_OUT_DATA) {
        uint16_t n = (uint16_t)(rd(d, 0x40017f14u) & 127u);
        if (n > 8 || n > d->total - d->transferred) {
            stall(d);
            return;
        }
        ranked_usb_io b = io(d);
        ranked_usb_ep0_receive(&b, d->reply.out_data + d->transferred, n);
        d->transferred += n;
        if (d->transferred == d->total || n < 8)
            status_in(d);
        else {
            d->in_state  = 0x3000;
            d->out_state = 0x30;
            wr(d, 0x40017ed4u, 0);
        }
    } else if (d->phase == RANKED_EP0_OUT_STATUS) {
        d->phase     = RANKED_EP0_IDLE;
        d->in_state  = 0x1000;
        d->out_state = 0x10;
    } else
        stall(d);
}
/* Native class reset callback 0x4858, invoked by raw event 4 at 0xed66.
 * This is endpoint rearming, not the PHY/controller initialization sequence. */
static void event4_reset(ranked_usb_device *d) {
#ifdef NKRO_ENABLE
    /* The original application only used IN1/2. The added NKRO interface
     * requires the IN4 gate as well; FIFO stores alone cannot enable it. */
    wr(d, 0x40017eb0u, 0x17);
#else
    wr(d, 0x40017eb0u, 7);
#endif
    wr(d, 0x40017f78u, (rd(d, 0x40017f78u) | 2u) & 63u);
    wr(d, 0x40017f78u, (rd(d, 0x40017f78u) | 4u) & 63u);
#ifdef NKRO_ENABLE
    /* Same operation as recovered native helper f200(endpoint4, true). */
    wr(d, 0x40017f78u, (rd(d, 0x40017f78u) | 0x10u) & 63u);
#endif
    wr(d, 0x40017eb4u, 9);
    wr(d, 0x40017f7cu, (rd(d, 0x40017f7cu) | 8u) & 63u);
    wr(d, 0x40017f2cu, 127);
    /* New control-engine caches cannot survive a reset. Native clears its
     * configuration and interface bytes, marks every endpoint ready, and
     * clears its transfer/frame markers; these fields are our representation. */
    memset(&d->setup, 0, sizeof d->setup);
    memset(&d->reply, 0, sizeof d->reply);
    d->phase            = RANKED_EP0_IDLE;
    d->in_state         = 0x1000;
    d->out_state        = 0x10;
    d->address          = 0;
    d->pending_address  = 0;
    d->configuration    = 0;
    d->apply_address    = false;
    d->need_zlp         = false;
    d->remote_wakeup    = false;
    d->suspended        = false;
    d->wakeup_requested = false;
    d->saw_frame        = false;
    ++d->reset_events;
    d->transferred = 0;
    d->total       = 0;
    for (unsigned ep = 0; ep < 6; ep++)
        d->ready[ep] = true;
    if (d->callbacks.configured) d->callbacks.configured(d->callbacks.context, 0);
}
static void power_state(ranked_usb_device *d, bool suspended) {
    if (d->suspended == suspended) return;
    d->suspended = suspended;
    if (suspended) d->wakeup_requested = false;
    if (suspended)
        ++d->suspend_events;
    else
        ++d->resume_events;
    if (d->callbacks.power) d->callbacks.power(d->callbacks.context, suspended);
}
static void event_irq(ranked_usb_device *d) {
    unsigned e = rd(d, 0x40016000u) & 31u;
    if (e == 0) {
        uint8_t saved[6] = {0};
        for (unsigned ep = 1; ep < 6; ep++)
            if (rd(d, 0x40017ed0u + ep * 8u) & 2u) {
                wr(d, 0x40017ed0u + ep * 8u, 2);
                saved[ep] = (uint8_t)(rd(d, 0x40017ed4u + ep * 8u) & 127u);
            }
        state(d, 0, true, 0x2000);
        state(d, 0, false, 0x20);
        wr(d, 0x40017eacu, 1);
        setup(d);
        wr(d, 0x40017f14u, 127);
        state(d, 0, true, d->in_state);
        state(d, 0, false, d->out_state);
        for (unsigned ep = 1; ep < 6; ep++)
            if (saved[ep]) wr(d, 0x40017ed4u + ep * 8u, saved[ep]);
    } else if (e == 6) {
        state(d, 0, true, 0x2000);
        wr(d, 0x40017ea4u, 1);
        in_complete(d);
        wr(d, 0x40017f14u, 127);
        state(d, 0, true, d->in_state);
    } else if (e == 7) {
        state(d, 0, false, 0x20);
        wr(d, 0x40017ea8u, 1);
        out_complete(d);
        wr(d, 0x40017f14u, 127);
        state(d, 0, false, d->out_state);
    } else if (e >= 8 && e <= 17) {
        unsigned ep = (e - 6) / 2;
        bool     in = (e & 1u) == 0;
        wr(d, in ? 0x40017ea4u : 0x40017ea8u, 1u << ep);
        if (in) {
            d->ready[ep] = true;
            state(d, ep, true, 0x2000);
        } else {
            uint16_t n = (uint16_t)(rd(d, 0x40017f14u + ep * 8u) & 127u);
            uint8_t  data[64];
            if (n <= 64) {
                if (ep == RANKED_USB_RAW_OUT_ENDPOINT) {
                    /* Original vendor OUT0x287c uses this proven FIFO. The
                     * runtime validates32-byte VIA packets before queueing. */
                    ranked_usb_io b = io(d);
                    ranked_usb_vendor_receive(&b, data, n);
                } else {
                    for (unsigned i = 0; i < n; i++)
                        data[i] = d->bus.read8(d->bus.context, 0x40017b00u - ep * 0x200u + i * 4u);
                }
                if (d->callbacks.packet) d->callbacks.packet(d->callbacks.context, ep, data, n);
            }
            state(d, ep, false, 0x40);
        }
    } else if (e >= 1 && e <= 4) {
        wr(d, 0x40017eacu, 1u << e);
        if (e == 4) event4_reset(d);
        if (e == 1) {
            d->saw_frame = true;
            ++d->frame_events;
            // A new SOF is direct evidence that the host bus is active again.
            power_state(d, false);
            if (d->callbacks.frame) d->callbacks.frame(d->callbacks.context);
        }
        if (e == 3) {
            // Native ed50 -> d4b4 -> 3f00 transitions configured state5 to
            // state3 after a frame was seen, and clears its frame marker.
            if (d->saw_frame && d->configuration) power_state(d, true);
            d->saw_frame = false;
        }
    }
    if (d->callbacks.event) d->callbacks.event(d->callbacks.context, e);
}
void ranked_usb_device_aux_irq(ranked_usb_device *d) {
    uint8_t flags = (uint8_t)rd(d, 0x40017f58u);
    ++d->aux_events;
    d->last_aux_flags = flags;
    /* Acknowledge the native auxiliary event. Host-driven resume ends the
     * software suspend state; remote wake is sent separately by the main-loop
     * task through ranked_usb_device_remote_wakeup(). */
    if (flags & 0x80u)
        wr(d, 0x40017f58u, 0x80);
    else if (flags & 0x08u) {
        controller_init(d);
        d->suspended     = false;
        d->saw_frame     = false;
        d->configuration = 0;
        if (d->callbacks.configured) d->callbacks.configured(d->callbacks.context, 0);
    } else if (d->suspended) {
        power_state(d, false);
    }
}
void ranked_usb_device_irq(ranked_usb_device *d) {
    uint32_t flags = rd(d, 0x40016008u);
    /* Original 0x3136/0x3148 re-read immediately before ACK. An event can
     * arrive after the test read; do not clear its pending bit using a cache. */
    if (flags & 1u) {
        wr(d, 0x40016008u, rd(d, 0x40016008u) & 2u);
        event_irq(d);
    }
    flags = rd(d, 0x40016008u);
    if (flags & 2u) {
        wr(d, 0x40016008u, rd(d, 0x40016008u) & 1u);
        ranked_usb_device_aux_irq(d);
    }
}
bool ranked_usb_device_send(ranked_usb_device *d, unsigned ep, const uint8_t *data, size_t n) {
    if (ep < 1 || ep > 5 || !d->configuration || d->suspended || !d->ready[ep]) return false;
    ranked_usb_io b = io(d);
    if (!data && n) return false;
    if (n > 64) return false;
    d->ready[ep] = false;
    return ranked_usb_fifo_submit(&b, ep, data, n);
}
bool ranked_usb_device_configured(const ranked_usb_device *d) {
    return d->configuration != 0 && !d->suspended;
}
bool ranked_usb_device_remote_wakeup(ranked_usb_device *d, uint32_t suspended_ms) {
    if (!d->configuration || !d->suspended || !d->remote_wakeup || d->wakeup_requested || suspended_ms < 5 || !d->bus.delay_ms || !d->bus.delay_original_short) return false;
    d->wakeup_requested = true;
    /* Native f328..f35a: prepare PHY, short7 settling, drive resume, release.
     * Use timed milliseconds for the pulse instead of naming native dd80
     * arguments milliseconds. Host SOF/aux events alone end software suspend. */
    wr(d, 0x40017f58u, (rd(d, 0x40017f58u) & 255u) | 2u);
    d->bus.delay_original_short(d->bus.context, 7);
    wr(d, 0x40017f58u, ((rd(d, 0x40017f58u) & 255u) & ~2u) | 1u);
    d->bus.delay_ms(d->bus.context, 7);
    wr(d, 0x40017f58u, (rd(d, 0x40017f58u) & 255u) & ~1u);
    return true;
}
