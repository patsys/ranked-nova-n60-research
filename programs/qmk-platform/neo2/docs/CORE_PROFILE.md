# Nova Neo2 core data

The candidate uses the existing three QMK/VIA layers and a normal **German
QWERTZ Windows host layout**. It is a keyboard-side remap; the QMK
`keymap_neo2.h` aliases alone would instead expect a Neo layout on the host.

| Internal layer | Role | Access |
|---|---|---|
| 0 | Neo letters and base keys | No Neo modifier |
| 1 | Supported Neo Mod3 symbols | Caps, physical #, or existing Fn2 |
| 2 | Neo navigation/digits with F-row compatibility | ISO <> key, right Alt, or existing Fn1 |

The physical letter rows become `x v l c w k h g f q ß`,
`u i a e o s n r t d y`, and `ü ö ä p z b m , . j`.
Standard controls and the62 populated matrix positions are retained.

This is **not complete six-level Neo2**. Greek/mathematical levels, Compose,
Neo lock combinations and keyboard mouse control are not implemented. The
candidate includes no Unicode helper, host driver installer or hardware change.

## Exact symbols instead of silent approximations

Common ASCII programming symbols and navigation use real QMK German aliases.
Unsupported Neo typography emits `KC_NO`; ellipsis is not replaced by a dot,
long-s is not replaced by s, superscript1 is not replaced by1, and inverted
punctuation/minus-sign are not replaced by visually similar ASCII characters.
The unavailable entries are listed in `core_keymap.json` and the audited direct
German-HID chord set is recorded in `layoutdata/german_host_availability.json`.

`shift_overrides.json` contains16 canonical Shift exceptions. Exactly four have
supported direct German-host targets: Shift+Neo1→°, Shift+Neo2→§,
Shift+Neo6→$, Shift+Neo7→€. The twelve unsupported targets are consumed as
`KC_NO`: ℓ,»,«,„,“,”,—,dead cedilla,ẞ,dead tilde,–,•. Ordinary Neo letters,
including ü/ö/ä, retain native Shift capitalization.

The candidate matrix must be combined with the small keymap hook described by
that JSON; it does not implement the Shift exceptions by itself. The hook also
emits Mod3 literal `^` and backtick by tapping their German dead-key chord then
Space. Base-layer grave/acute accents remain dead keys. Handled releases must
remain suppressed if Shift or the layer changes between press and release.

For the60% board, Mod4's top number row supplies F1–F12 instead of canonical
Neo4 typography. Its keypad area emits ordinary digits/punctuation rather than
NumLock-dependent keypad codes. Space remains Space instead of canonical
keypad0. Esc is preserved in this candidate. A dedicated Neo T1 key left of1
does not exist on the recovered board; any Fn+Esc policy is a separate choice.

## Canonical sources, provenance and validation

Official Neo repository revision:
`cf36e07ce5ff22c51149c3ad933c71fcd770f613`.

- [Machine-readable Xmodmap](https://git.neo-layout.org/neo/neo-layout/src/commit/cf36e07ce5ff22c51149c3ad933c71fcd770f613/linux/xmodmap/neo_de.xmodmap)
- [Independent six-level reference diagrams](https://git.neo-layout.org/neo/neo-layout/src/commit/cf36e07ce5ff22c51149c3ad933c71fcd770f613/A-REFERENZ-A/neo20.txt)
- [Official layer explanation](https://www.neo-layout.org/Benutzerhandbuch/Tastaturbelegung/)
- [Official licensing policy](https://www.neo-layout.org/Beitragen/Lizenzfragen/)

Pinned source copies and SHA256 hashes are retained in `layoutdata/upstream`.
The repository contains GPLv3 `COPYING`; project policy assigns driver code to
GPLv3 and reference text/images to CC-BY-SA3.0Germany. Vendored X11 keysym
definitions retain their Open Group/DEC permissive notices.

`extract_canonical.py` reorders the Xmodmap's unusual1,2,3,5,4,4+Shift,6 sequence
and independently checks **276 cells** against the six reference diagrams. It
preserves Unicode, keypad/navigation actions, dead keys and unassigned positions
as different data types. It then maps62 recovered physical matrix positions.
`validate_core_candidate.py` compiles the separate396-byte, three-layer data
table with actual QMK macros and checks supported/unavailable entries.

These scripts do not modify the active keymap, runtime, build configuration or
device. The root task owns integration and any authorized hardware operation.
