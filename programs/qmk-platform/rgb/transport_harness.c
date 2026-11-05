// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later
#include "nova_rgb_transport.h"
#include <stddef.h>
nova_rgb_transport test_transport;
uint8_t test_colors[6][11][3];
uint32_t test_ticks;
static uint32_t read32(uintptr_t a) { return *(volatile uint32_t *)a; }
static void write32(uintptr_t a,uint32_t v) { *(volatile uint32_t *)a=v; }
void rgb_test_delay(uint32_t units) { (void)units; }
static uint32_t ticks(void) { return test_ticks; }
int rgb_test_init(void) {
    const nova_rgb_io io={read32,write32,rgb_test_delay,ticks};
    return nova_rgb_transport_init(&test_transport,&io);
}
int rgb_test_submit(void) { return nova_rgb_transport_submit(&test_transport,test_colors); }
void rgb_test_poll(void) { nova_rgb_transport_poll(&test_transport); }
uintptr_t rgb_test_get(unsigned index) {
    switch(index) {
        case 0:return (uintptr_t)test_transport.tx;
        case 1:return (uintptr_t)test_transport.rx;
        case 2:return test_transport.ready;
        case 3:return test_transport.active;
        case 4:return test_transport.submitted;
        case 5:return test_transport.completed;
        case 6:return test_transport.errors;
        case 7:return test_transport.skipped;
        default:return 0;
    }
}
void *memset(void *p,int value,size_t n) {
    unsigned char *q=p;while(n--) *q++=(unsigned char)value;return p;
}
