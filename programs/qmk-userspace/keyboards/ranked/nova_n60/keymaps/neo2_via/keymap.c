// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

/* Neo2 CORE candidate for a standard German host; NOT complete six-layer Neo2.
 * Requires the Shift/literal-dead-key hook described by shift_overrides.json.
 * See core_keymap.json for explicit unavailable typography/F-row deviations.
 * Canonical Neo reference: commit cf36e07ce5ff22c51149c3ad933c71fcd770f613.
 */
#include QMK_KEYBOARD_H
#include "keymap_german.h"
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [0] =
        {
            {KC_ESC, DE_1, DE_2, DE_3, DE_4, DE_5, DE_6, DE_7, DE_8, DE_9,
             DE_0},
            {KC_TAB, DE_X, DE_V, DE_L, DE_C, DE_W, DE_K, DE_H, DE_G, DE_F,
             DE_Q},
            {MO(1), DE_U, DE_I, DE_A, DE_E, DE_O, DE_S, DE_N, DE_R, DE_T, DE_D},
            {KC_LSFT, MO(2), DE_UDIA, DE_ODIA, DE_ADIA, DE_P, DE_Z, DE_B, DE_M,
             DE_COMM, DE_DOT},
            {KC_LCTL, KC_LGUI, KC_LALT, KC_SPC, MO(2), MO(2), MO(1), KC_RCTL,
             DE_J, KC_NO, KC_RSFT},
            {KC_NO, DE_MINS, DE_GRV, KC_BSPC, DE_SS, DE_ACUT, KC_NO, DE_Y,
             MO(1), KC_ENT, KC_NO},
        },
    [1] =
        {
            {KC_ESC, KC_NO, DE_SUP2, DE_SUP3, KC_NO, KC_NO, KC_NO, KC_NO, KC_NO,
             KC_NO, KC_NO},
            {KC_TAB, KC_NO, DE_UNDS, DE_LBRC, DE_RBRC, DE_CIRC, DE_EXLM,
             DE_LABK, DE_RABK, DE_EQL, DE_AMPR},
            {MO(1), DE_BSLS, DE_SLSH, DE_LCBR, DE_RCBR, DE_ASTR, DE_QUES,
             DE_LPRN, DE_RPRN, DE_MINS, DE_COLN},
            {KC_LSFT, MO(2), DE_HASH, DE_DLR, DE_PIPE, DE_TILD, DE_GRV, DE_PLUS,
             DE_PERC, DE_DQUO, DE_QUOT},
            {KC_LCTL, KC_LGUI, KC_LALT, KC_SPC, MO(2), MO(2), MO(1), KC_RCTL,
             DE_SCLN, KC_NO, KC_RSFT},
            {KC_NO, KC_NO, KC_NO, KC_BSPC, KC_NO, KC_NO, KC_NO, DE_AT, MO(1),
             KC_ENT, KC_NO},
        },
    [2] =
        {
            {KC_ESC, KC_F1, KC_F2, KC_F3, KC_F4, KC_F5, KC_F6, KC_F7, KC_F8,
             KC_F9, KC_F10},
            {KC_TAB, KC_PGUP, KC_BSPC, KC_UP, KC_DEL, KC_PGDN, KC_NO, DE_7,
             DE_8, DE_9, DE_PLUS},
            {MO(1), KC_HOME, KC_LEFT, KC_DOWN, KC_RGHT, KC_END, KC_NO, DE_4,
             DE_5, DE_6, DE_COMM},
            {KC_LSFT, MO(2), KC_ESC, KC_TAB, KC_INS, KC_ENT, LCTL(DE_Z),
             DE_COLN, DE_1, DE_2, DE_3},
            {KC_LCTL, KC_LGUI, KC_LALT, KC_SPC, MO(2), MO(2), MO(1), KC_RCTL,
             DE_SCLN, KC_NO, KC_RSFT},
            {KC_NO, KC_F11, KC_F12, KC_BSPC, KC_NO, KC_NO, KC_NO, DE_DOT, MO(1),
             KC_ENT, KC_NO},
        },
};

/* Standard QMK overrides: only Neo base level, preserving normal letters. */
#include "process_key_override.h"
const key_override_t neo_shift_0 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_1, DE_DEG, 1u);
const key_override_t neo_shift_1 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_2, DE_SECT, 1u);
const key_override_t neo_shift_2 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_3, KC_NO, 1u);
const key_override_t neo_shift_3 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_4, KC_NO, 1u);
const key_override_t neo_shift_4 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_5, KC_NO, 1u);
const key_override_t neo_shift_5 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_6, DE_DLR, 1u);
const key_override_t neo_shift_6 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_7, DE_EURO, 1u);
const key_override_t neo_shift_7 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_8, KC_NO, 1u);
const key_override_t neo_shift_8 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_9, KC_NO, 1u);
const key_override_t neo_shift_9 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_0, KC_NO, 1u);
const key_override_t neo_shift_10 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_COMM, KC_NO, 1u);
const key_override_t neo_shift_11 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_DOT, KC_NO, 1u);
const key_override_t neo_shift_12 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_MINS, KC_NO, 1u);
const key_override_t neo_shift_13 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_GRV, KC_NO, 1u);
const key_override_t neo_shift_14 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_SS, KC_NO, 1u);
const key_override_t neo_shift_15 =
    ko_make_with_layers(MOD_MASK_SHIFT, DE_ACUT, KC_NO, 1u);
const key_override_t *key_overrides[] = {
    &neo_shift_0,  &neo_shift_1,  &neo_shift_2,  &neo_shift_3,
    &neo_shift_4,  &neo_shift_5,  &neo_shift_6,  &neo_shift_7,
    &neo_shift_8,  &neo_shift_9,  &neo_shift_10, &neo_shift_11,
    &neo_shift_12, &neo_shift_13, &neo_shift_14, &neo_shift_15,
};

/* Neo exposes each level modifier on both hands. Track physical sources so
 * releasing one MO key cannot cancel another still-held source for that level.
 * The Fn keys use the same standard layer keycodes and are tracked as well.
 */
static uint16_t neo_layer_sources[2][MATRIX_ROWS];
bool process_record_user(uint16_t keycode, keyrecord_t *record) {
  if (keycode != MO(1) && keycode != MO(2))
    return true;
  const uint8_t row = record->event.key.row, col = record->event.key.col;
  if (row >= MATRIX_ROWS || col >= MATRIX_COLS)
    return true;
  const uint8_t group = keycode == MO(1) ? 0 : 1;
  const uint16_t bit = (uint16_t)1u << col;
  if (record->event.pressed)
    neo_layer_sources[group][row] |= bit;
  else
    neo_layer_sources[group][row] &= (uint16_t)~bit;
  bool held = false;
  for (uint8_t i = 0; i < MATRIX_ROWS; ++i)
    held |= neo_layer_sources[group][i] != 0;
  if (held)
    layer_on(group + 1u);
  else
    layer_off(group + 1u);
  return false;
}
