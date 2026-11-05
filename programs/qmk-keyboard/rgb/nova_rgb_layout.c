// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later
#ifdef RGB_MATRIX_ENABLE
#    include "rgb_matrix.h"

// LED centers follow the keyboard.json physical ISO layout.
led_config_t g_led_config = {{
                                 {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
                                 {11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21},
                                 {22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32},
                                 {33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43},
                                 {44, 45, 46, 47, 48, 49, 50, 51, 52, NO_LED, 53},
                                 {NO_LED, 54, 55, 56, 57, 58, NO_LED, 59, 60, 61, NO_LED},
                             },
                             {
                                 {7, 0}, {22, 0}, {37, 0}, {52, 0}, {67, 0}, {82, 0}, {97, 0}, {112, 0}, {127, 0}, {142, 0}, {157, 0}, {11, 16}, {30, 16}, {45, 16}, {60, 16}, {75, 16}, {90, 16}, {105, 16}, {119, 16}, {134, 16}, {149, 16}, {164, 16}, {13, 32}, {34, 32}, {49, 32}, {63, 32}, {78, 32}, {93, 32}, {108, 32}, {123, 32}, {138, 32}, {153, 32}, {168, 32}, {9, 48}, {26, 48}, {41, 48}, {56, 48}, {71, 48}, {86, 48}, {101, 48}, {116, 48}, {131, 48}, {146, 48}, {161, 48}, {9, 64}, {28, 64}, {47, 64}, {103, 64}, {159, 64}, {177, 64}, {196, 64}, {215, 64}, {175, 48}, {203, 48}, {172, 0}, {187, 0}, {209, 0}, {179, 16}, {194, 16}, {183, 32}, {198, 32}, {215, 24},
                             },
                             {
                                 LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
                                 LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT, LED_FLAG_KEYLIGHT,
                             }};
#endif
