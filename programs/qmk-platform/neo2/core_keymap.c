/* Neo2 CORE candidate for a standard German host; NOT complete six-layer Neo2.
 * Requires the Shift/literal-dead-key hook described by shift_overrides.json.
 * See core_keymap.json for explicit unavailable typography/F-row deviations.
 * Canonical Neo reference: commit cf36e07ce5ff22c51149c3ad933c71fcd770f613.
 */
#include QMK_KEYBOARD_H
#include "keymap_german.h"
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] = {
        {KC_ESC, DE_1, DE_2, DE_3, DE_4, DE_5, DE_6, DE_7, DE_8, DE_9, DE_0},
        {KC_TAB, DE_X, DE_V, DE_L, DE_C, DE_W, DE_K, DE_H, DE_G, DE_F, DE_Q},
        {MO(1), DE_U, DE_I, DE_A, DE_E, DE_O, DE_S, DE_N, DE_R, DE_T, DE_D},
        {KC_LSFT, MO(2), DE_UDIA, DE_ODIA, DE_ADIA, DE_P, DE_Z, DE_B, DE_M, DE_COMM, DE_DOT},
        {KC_LCTL, KC_LGUI, KC_LALT, KC_SPC, MO(2), MO(2), MO(1), KC_RCTL, DE_J, KC_NO, KC_RSFT},
        {KC_NO, DE_MINS, DE_GRV, KC_BSPC, DE_SS, DE_ACUT, KC_NO, DE_Y, MO(1), KC_ENT, KC_NO},
    },
    [1] = {
        {KC_ESC, KC_NO, DE_SUP2, DE_SUP3, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO},
        {KC_TAB, KC_NO, DE_UNDS, DE_LBRC, DE_RBRC, DE_CIRC, DE_EXLM, DE_LABK, DE_RABK, DE_EQL, DE_AMPR},
        {MO(1), DE_BSLS, DE_SLSH, DE_LCBR, DE_RCBR, DE_ASTR, DE_QUES, DE_LPRN, DE_RPRN, DE_MINS, DE_COLN},
        {KC_LSFT, MO(2), DE_HASH, DE_DLR, DE_PIPE, DE_TILD, DE_GRV, DE_PLUS, DE_PERC, DE_DQUO, DE_QUOT},
        {KC_LCTL, KC_LGUI, KC_LALT, KC_SPC, MO(2), MO(2), MO(1), KC_RCTL, DE_SCLN, KC_NO, KC_RSFT},
        {KC_NO, KC_NO, KC_NO, KC_BSPC, KC_NO, KC_NO, KC_NO, DE_AT, MO(1), KC_ENT, KC_NO},
    },
    [2] = {
        {KC_ESC, KC_F1, KC_F2, KC_F3, KC_F4, KC_F5, KC_F6, KC_F7, KC_F8, KC_F9, KC_F10},
        {KC_TAB, KC_PGUP, KC_BSPC, KC_UP, KC_DEL, KC_PGDN, KC_NO, DE_7, DE_8, DE_9, DE_PLUS},
        {MO(1), KC_HOME, KC_LEFT, KC_DOWN, KC_RGHT, KC_END, KC_NO, DE_4, DE_5, DE_6, DE_COMM},
        {KC_LSFT, MO(2), KC_ESC, KC_TAB, KC_INS, KC_ENT, LCTL(DE_Z), DE_COLN, DE_1, DE_2, DE_3},
        {KC_LCTL, KC_LGUI, KC_LALT, KC_SPC, MO(2), MO(2), MO(1), KC_RCTL, DE_SCLN, KC_NO, KC_RSFT},
        {KC_NO, KC_F11, KC_F12, KC_BSPC, KC_NO, KC_NO, KC_NO, DE_DOT, MO(1), KC_ENT, KC_NO},
    },
};
