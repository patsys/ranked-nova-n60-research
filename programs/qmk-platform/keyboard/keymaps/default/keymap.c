/* Generated from original fallback tables f6a2/f79e/f89a.
 * Original FF/FE momentary selectors map to MO(2)/MO(1), preserving FF priority.
 * Unsupported vendor actions are KC_NO. User mutable remaps are not imported.
 */
#include QMK_KEYBOARD_H
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = {
        {0x0029, 0x001e, 0x001f, 0x0020, 0x0021, 0x0022, 0x0023, 0x0024, 0x0025, 0x0026, 0x0027},
        {0x002b, 0x0014, 0x001a, 0x0008, 0x0015, 0x0017, 0x001c, 0x0018, 0x000c, 0x0012, 0x0013},
        {0x0039, 0x0004, 0x0016, 0x0007, 0x0009, 0x000a, 0x000b, 0x000d, 0x000e, 0x000f, 0x0033},
        {0x00e1, 0x0064, 0x001d, 0x001b, 0x0006, 0x0019, 0x0005, 0x0011, 0x0010, 0x0036, 0x0037},
        {0x00e0, 0x00e3, 0x00e2, 0x002c, 0x00e6, MO(2), MO(1), 0x00e4, 0x0038, KC_NO, 0x00e5},
        {KC_NO, 0x002d, 0x002e, 0x002a, 0x002f, 0x0030, KC_NO, 0x0034, 0x0032, 0x0028, KC_NO},
    },
    [2] = {
        {0x0035, 0x003a, 0x003b, 0x003c, 0x003d, 0x003e, 0x003f, 0x0040, 0x0041, 0x0042, 0x0043},
        {KC_NO, KC_NO, 0x0052, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, 0x0046, 0x004a, 0x004d},
        {KC_NO, 0x0050, 0x0051, 0x004f, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, 0x004b},
        {KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, 0x0049},
        {KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, MO(2), MO(1), KC_NO, 0x004c, KC_NO, KC_NO},
        {KC_NO, 0x0044, 0x0045, KC_NO, KC_NO, KC_NO, KC_NO, 0x004e, KC_NO, KC_NO, KC_NO},
    },
    [1] = {
        {KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO},
        {KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO},
        {KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO},
        {KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO},
        {KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, MO(2), MO(1), KC_NO, KC_NO, KC_NO, KC_NO},
        {KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO},
    },
};
