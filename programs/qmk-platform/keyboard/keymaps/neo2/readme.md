# Neo2 core for German Windows

Separate keymap; QMK core and recovered hardware drivers are unchanged.
Neo levels1/2 use the base map and Shift; levels3/4 use MO(1)/MO(2).
Caps/# select Mod3, ISO<>/rightAlt select Mod4. Existing Fn keys also provide
these layers. The Mod4 number row suppliesF1–F12 for this60% keyboard.

Standard QMK Key Overrides implement the available Neo Shift punctuation.
The keymap-local `process_record_user` hook tracks the physical Mod3/Mod4
sources, so releasing one side keeps the level active while the other is held.
It passes all other keys through to QMK. No QMK core patch is required.
Characters unavailable through ordinary German QWERTZ HID chords are disabled,
not replaced with similar-looking ASCII. Greek/math levels5/6 are not included.
German circumflex/grave remain dead keys: press Space afterward for a literal
accent. This helper-free core is not a fully conformant complete Neo2 driver.

Full mapping, exceptions and upstream source/license records are under
`qmk_port/neo2/`. The user explicitly selected German QWERTZ and no Windows
Unicode helper. VIA mappings are volatile on this port; the compiled keymap
is the reset/power-up default. Use `--keymap neo2 --via --diagnostic` with the
research build script. Upstream QMK uses this keymap's `rules.mk` normally.
