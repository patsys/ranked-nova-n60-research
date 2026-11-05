// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later
#ifdef RGB_MATRIX_ENABLE
#include "rgb_matrix.h"
#include "timer.h"
#include "nova_rgb_transport.h"
#include "recovered_scan.h"
#include <string.h>

static nova_rgb_transport transport;
static uint8_t colors[6][11][3];
extern void nova_platform_delay_original_units(uint32_t units);
static uint32_t read32(uintptr_t a) { return *(volatile uint32_t *)a; }
static void write32(uintptr_t a,uint32_t v) { *(volatile uint32_t *)a=v; }
static void init(void) {
    const nova_rgb_io io={read32,write32,nova_platform_delay_original_units,timer_read32};
    memset(colors,0,sizeof(colors));
    nova_rgb_transport_init(&transport,&io);
}
static void set_color(int index,uint8_t r,uint8_t g,uint8_t b) {
    if (index<0 || index>=RGB_MATRIX_LED_COUNT) return;
    for (unsigned row=0;row<6;++row)
        for (unsigned col=0;col<11;++col)
            if (g_led_config.matrix_co[row][col]==index) {
                colors[row][col][0]=r;colors[row][col][1]=g;colors[row][col][2]=b;
                return;
            }
}
static void set_color_all(uint8_t r,uint8_t g,uint8_t b) {
    for (int i=0;i<RGB_MATRIX_LED_COUNT;++i) set_color(i,r,g,b);
}
static void flush(void) { nova_rgb_transport_submit(&transport,colors); }
const rgb_matrix_driver_t rgb_matrix_driver={init,set_color,set_color_all,flush};

/* Only cached state; called from the existing read-only diagnostic VIA hook. */
void nova_rgb_diagnostic(uint8_t *data) {
    data[0]=1;data[1]=transport.ready;data[2]=transport.active;data[3]=transport.last_reply;
    const uint32_t values[]={transport.submitted,transport.completed,transport.errors,transport.skipped};
    for (unsigned i=0;i<4;++i)
        for (unsigned byte=0;byte<4;++byte) data[5+4*i+byte]=(uint8_t)(values[i]>>(24-8*byte));
    data[21]=rgb_matrix_get_mode();data[22]=rgb_matrix_get_hue();
    data[23]=rgb_matrix_get_sat();data[24]=rgb_matrix_get_val();data[25]=rgb_matrix_is_enabled();
}
#endif
