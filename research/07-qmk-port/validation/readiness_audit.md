# Historical snapshot (superseded)

This copied audit contains earlier contradictory persistence conclusions. The final 5 November probe failed persistence; use `docs/STATUS.md` and `research/07-qmk-port/validation/via_persistence_audit.json` as current status.

---

# QMK contribution preparation

## VIA persistence passed on hardware, 4 November 2026

On the installed gate-clear candidate image, `validate_via_persistence.py`
churned layer 2 over VIA until QMK wear-leveling consolidated (log wrapped from
0xF60 to 0x46C). Every write reported stage 5, and post-consolidation writes
require erased cells, so the F8-FF erase path works. Layer 2 was restored and
marker [2,4,9]=0x0005 set. After a user USB unplug/replug (diagnostic RAM reset
to zero, proving a restart) all 66 layer-2 slots matched
(`via_persistence_replug_check_20261104.json`).

The earlier "failure" was a probe artefact: `0x1F408` was already present in the
pre-flash dump, and the bootloader dump of F8-FF does not reflect what the
application reads (the app found its log after a cold restart). Settings are
expected to be lost on bootloader entry/reflash; document this in the readme.

## Latest persistence result: raw flash and runtime reports disagree, 4 November 2026

The QMK CLI flash passed full readback with the bootloader, outside-application
flash, and hidden metadata unchanged. A temporary read-only diagnostic found the
old failure: the page-gate register reads `0xFFFFFFFF`, causing an invalid
precondition to reject writes before the controller command. The updated source
uses only the metadata permission bitmap and F8-FF range check, then sets and
clears the gate following the recovered vendor stub.

The latest live VIA write immediately returned `0x0004`; diagnostic stage 5
reported a successful controller write, and one cold restart returned `0x0004`.
But after a read-only full-flash probe reset the app, the slot returned `0x0001`.
The raw dump shows only three changed bytes at `0x1F408`; the diagnostic-reported
word at `0x1F744` is erased. Persistence is not reliable, so the PR gate stays
closed until the address/replay mismatch is resolved. See
`via_persistence_audit.json` and `persistence_backend_validation_20261103.json`.

## Candidate correction ready for hardware retest

The recovered vendor stub clears only the selected page-gate bit with
read-modify-write; the QMK driver had written zero to the whole register. Both
erase and program paths now clear only the selected bit. Default and VIA builds
passed, default lint passed, and the candidate HEX passed the flasher's offline
bounds check (`0x2000..0x94b7`, 29,880 bytes). It has not yet been flashed; the
keyboard must enter its original bootloader with Esc held during reconnect.
No PR until the controlled test and read-only raw-flash verification agree.

The separate transient-EEPROM remote-wake build previously passed the Windows
key-wake test on one host and keyboard. It does not validate persistent storage.
The PR gate remains closed until persistent storage passes, flasher distribution
instructions are public, regression tests cover the backend, and the final
contribution audit is complete. Neo2-specific keymaps remain excluded. Earlier
candidate notes below are historical.

The previously installed standard Neo2/VIA image remains on the keyboard; the
new power-handling candidate has not been flashed. The user confirmed typing,
moving rainbow and cold start on that installed image. The user reported that
lighting remained on during a Windows Sleep test; actual bus suspend was not
measured in that trial. Accidental characters afterward were explained by the
keyboard physically falling, not a reported firmware failure.

The candidate defers controller power events to the main loop, calls QMK suspend
and resume hooks, enables RGB Matrix sleep, and pauses acquisition during
suspend. Nine offline controller assertions and seventeen linked RGB/VIA tests
pass, including black-frame submission and restoration of the previous RGB
configuration. These are modeled tests, not physical timing/current evidence.
The Nova default and Neo2/VIA images build. The full inherited one-key target
exposed a parent media-key setting; a local explicit override is being tested.
The candidate still requires final build/regression checks and physical USB
sleep/resume validation. No PR is authorized for creation until the required
checks pass. The historical sections below describe earlier image revisions.

Requested by the user on 3 November 2026. Token authentication succeeded as
`patsys`; the token is read only from the user's home file at request time and
must never be included in commits, URLs, logs or PR text.

Forks are available:

- https://github.com/patsys/qmk_firmware
- https://github.com/patsys/qmk_userspace

An isolated local firmware worktree is on `ranked-nova-platform`, based on
upstream `develop` commit `b98c12c096a801bce22d30f7933f5be0c07235e7`.
The installed-image source checkout is not switched or modified in QMK core.
No pull request has been created yet.

## Required separation

The official contribution rules and PR checklist require small logical changes,
standard builds, valid source licensing and a test board for new MCU/platform
support. Core/platform PRs target `develop`; keyboard support follows separately.
The pristine keyboard default remains conventional ISO and does not enable VIA.
Personal keymaps, including Neo2, are out of scope for the QMK firmware PR. VIA
definitions belong in the VIA keyboard repository rather than QMK firmware.

References:

- https://docs.qmk.fm/contributing
- https://docs.qmk.fm/pr_checklist
- https://docs.qmk.fm/hardware_keyboard_guidelines

## Current contribution state

The new local port builds through the QMK CLI for the generic ISO default. It
provides an experimental RY7203 platform, one-key target, separate Nova keyboard,
standard Raw HID and RGB Matrix. Neo2-specific keymaps are excluded from the QMK
firmware contribution. The reported chip
marking is RY7203 N48C-C 2214-CC; its public register specification and manufacturer
identity are still unverified. No unrelated MCU is selected to bypass validation.

All three final build commands exited successfully. QMK lint passed for the
conventional default, external Neo2/VIA and one-key targets. The final ELF hashes
match their actual linked-image test results: 131 default cases, four one-key
cases, 113 Neo2 key cases, 219 VIA cases, 15 RGB/VIA cases and the two timer startup
regression cases. The source audit checked 41 C/header files for licensing and
formatting, lowercase names (with QMK's .S assembly convention), and JSON syntax.
These checks are offline and do not establish new physical firmware behavior.

The PR gate is NOT passed. Generic ISO default compile/lint and QMK wear-leveling
tests pass; fresh-install flasher packaging and the `qmk flash --check-image`
route pass without USB access. A public flasher release, Nova-specific flash
driver tests, and persistent-settings cold-power validation remain required.
Windows wake-on-key has passed once on the transient-EEPROM image. Neo2 keymaps
are excluded from the QMK firmware PR. See features_and_gaps.md and
flashing_requirements.md for precise scope.

Stock firmware was physically restored and fully readback-verified before the
new QMK tests. The current image is the transient-EEPROM wake-test build.
Nothing has been pushed and no PR has been opened. Platform/test-board, Nova
keyboard, and personal/VIA keymaps must remain separate logical submissions.
The userspace keymaps currently exist locally; the previously created GitHub
userspace fork has not been populated.

Only authored source and necessary configuration/documentation are candidates
for commits. Tokens, decrypted vendor firmware, encryption keys, update captures,
SQLite databases, tool installations and generated firmware binaries are outside
the contribution. Existing third-party copyright notices must be preserved.
