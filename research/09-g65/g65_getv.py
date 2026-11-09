# Copyright 2026 patsys
# SPDX-License-Identifier: GPL-3.0-or-later
"""G65: stock boot-entry (04 a5 01) then a single bootloader GETV. Nothing else is sent."""
import ctypes, json, sys, time
import hid

ctypes.CDLL(hid.__file__).hid_darwin_set_open_exclusive(0)
QUERY = bytes.fromhex("0000000004000001") + b"getv"
log = {"before": [(hex(d["vendor_id"]), hex(d["product_id"]), hex(d["usage_page"])) for d in hid.enumerate(0x3532, 0xA0C2)]}

vendor = [d for d in hid.enumerate(0x3532, 0xA0C2) if d["usage_page"] == 0xFF00]
assert len(vendor) == 1 and not hid.enumerate(0x352D, 0), "Expected stock G65 only"
app = hid.device()
app.open_path(vendor[0]["path"])
try:
    log["entry_written"] = app.write(bytes.fromhex("04a501") + bytes(61))
finally:
    app.close()

boots = []
for _ in range(100):
    boots = hid.enumerate(0x352D, 0)
    if boots:
        break
    time.sleep(0.1)
log["after_entry"] = {
    "bootloader": [(hex(d["vendor_id"]), hex(d["product_id"]), hex(d["usage_page"]), d["product_string"]) for d in boots],
    "application_left": len(hid.enumerate(0x3532, 0xA0C2)),
}
if len(boots) != 1:
    print(json.dumps(log, indent=1)); sys.exit("No single bootloader interface; nothing further sent")

h = hid.device()
h.open_path(boots[0]["path"])
try:
    assert h.write(b"\0" + QUERY.ljust(64, b"\0")) == 65
    reply = bytes(h.read(65, 2000))
finally:
    h.close()
reply = reply[1:] if len(reply) == 65 and reply[0] == 0 else reply
log["getv_reply_hex"] = reply.hex()
if reply[8:16] == b"version:":
    log["hardware_id"] = hex(reply[16])
    log["version_fields"] = [reply[16:20].hex(), reply[20:24].hex()]
print(json.dumps(log, indent=1))
