# Read-only running-firmware sensor query

Latest physical outcome: the query identified unstable late-channel readings.
A conversion-window correction restored sustained readings and user-confirmed
typing; see `qmk_port/neo2/TIMING_FIX_20261103.md`. The chronological notes below
retain the earlier inconclusive RAM experiment.

Enabled only in the research `NOVA_USB_DIAGNOSTIC` VIA build. QMK core is
unchanged. The keyboard's existing `via_command_kb` hook handles the request;
the matrix accessor copies cached acquisition state without MMIO access.
This is a research extension, not an upstream VIA protocol claim.

Send a 32-byte VIA packet beginning `02 80 bank`, zero-padded. A valid bank is
0–5. Reply bytes:

| Bytes | Meaning |
| --- | --- |
| 0–2 | Echoed command, value ID and bank |
| 3 | Format version 1 |
| 4 | 1 initialized; 0 uninitialized; FF invalid bank |
| 5 | Reserved, zero |
| 6–7 | Raw hysteresis row, big-endian |
| 8–29 | Eleven cached uint16 sensor samples, big-endian |
| 30–31 | QMK debounced row, big-endian |

Invalid banks return zero bytes 5–31. No arbitrary-address access, calibration
write, threshold change, erase or programming operation is exposed. The normal
main loop handles the query between matrix tasks. Consecutive bank queries are
separate snapshots, not one atomic six-bank scan.

`qmk_port/neo2/capture_live_sensors.py` requests explicit snapshots. The linked
VIA pipeline test checks all six idle banks, invalid banks 6/255, and held L/Ö
samples/rows, including absence of query MMIO writes.

## Why the legacy RAM capture was inconclusive

The 3 November capture at
`qmk_flash/ram_scan/key_diagnostic_20261103T144925_139264Z/result.json`
returned zero samples everywhere while the user held K/L/Ö. It returned to QMK
successfully. This older payload does not perform the full cold-start clock
calibration/settling sequence and was originally demonstrated after stock-app
initialization. These zeros do not establish a broken sensor, threshold or
specific missing initialization. Querying the actual running firmware avoids
that mismatch. Root cause remains pending live measurements.
