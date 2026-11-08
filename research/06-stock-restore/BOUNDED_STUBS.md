# Bounded stock restore RAM stubs

The stub binaries are not included because they are patched vendor code; their builders and validation results are. These are440-byte vendor-derived stubs for the exact recovered bootloader ABI. They admit only pages16..132,512-byte DATA, packet context0x20000324, and program source0x2000032c. Original erase/program/timing bodies and native ABI helpers are retained. Special metadata erase/program entries0xda/0xfc return2. Initialization clears RAM crypto flag0x20000214 and preserves the original timing routine's clock argument and stack prologue.

## Versions and protocol constraints

* V1 SHA256 `5f741245d37bd3066e108385e95e3589aecf20d5f48d381a45d231225808b37f`: operation bounds pass, but native DATA remains active. A following reader START gets NACK5 and native return4. It is unsuitable for the proposed in-session readback flow.
* V2 SHA256 `1a72d7cccea5043d144744f3c67ff9070af8e6961fb2bf729a2071a34a42da18`: after all guards pass, last page132 clears the native outer active local. This permits subsequent read-only STARTs without COMPLETE. It does not protect against the native error/timeout path resetting toward application execution.
* V3 SHA256 `e4c466571f03c5ece7ae4417c281dd9be3787d659945633acec7cfb92dae3a8c`: retains V2 handoff and, before every admitted erase command, replaces the outer saved caller return with0x849. Native error/timeout returns to the original USB bootstrap at0x848 with restored caller SP/R4–R7. This is one reentry, not indefinite recovery or power-loss protection. A new native outer session again starts with its normal return unless a separate hold mechanism renews protection.

V3's original bootloader return0x87f must be restored by a separately validated release stub **after readback verification**, before using normal cleanup to return to the application. The ordinary reader alone deliberately retains the0x849 saved return. No COMPLETE command belongs to this application-only flow.

## Reproducible offline checks

Run builders and validators using the bundled Python with workspace`.tools` dependencies:

```powershell
python stock_restore/build_bounded_stub_v3.py
python stock_restore/validate_protocol_transition.py --v3
python stock_restore/validate_failure_reentry_v3.py
python stock_restore/validate_protocol_transition.py --release
```

The builder executes all117 pages through both operations (234 accepted operations), boundary/length/context/source rejection tests, and exact saved-return/active-local write checks. Rejected operations issue no controller writes. Program stores match all128 source words per accepted page.

The full protocol model keeps the captured first52 START bytes unchanged, including clear length0x1cc00, supplies the original accepted decoded metadata as an explicit crypto fixture, and sends the actual117-page prepared stock body. All14976 controller data words match stock. V2/V3 subsequently execute actual reader stubs against original native control flow; boot bytes, application bytes, and separately mapped hidden metadata each return the expected56-byte response.

The failure model executes native error and1000 empty receive polls after one accepted DATA page. Original delay helper0x9bc is skipped only to accelerate timeout. Both paths reach0x848, restore caller SP/R4–R7, and avoid0x24c. Tests stop before physical USB initialization, and do not prove a host can reconnect after a real controller reinitialization.

The combined release model executes the actual117 stock pages, three read-only START replies, `release_stub.bin` (SHA256 `57332cb094949feeba32c44fa829bb57069eaef61d92bceab161601737af4323`), then GETV directly. The guarded native F00 initialization stack write restores the caller0x849 ->0x87f at SP+116. GETV is rejected in the now-active normal START state, returning4 through0x87e to the normal reset routine0x24c. The caller stack and R4–R7 match the original main fixture. No additional flash-controller commands occur beyond117 erases/14976 program words, all ordinary word addresses0x800..0x427f; hidden metadata remains unchanged in the model. The test stops at0x24c before physical reset. This proof is `protocol_release_v3_validation.json`; it does not predict a real USB re-enumeration result.

Native guard magic and controller busy-clear fixtures are explicit. Controller registers are emulated RAM; flash contents are not changed by these tests. Physical erase/program success, hardware permission bits, reconnect timing, and power-loss recovery remain outside these offline proofs. Production host code must check the exact binary hash and validation records, use the known bootloader ABI, and verify device readback rather than infer success from native ACK4.
