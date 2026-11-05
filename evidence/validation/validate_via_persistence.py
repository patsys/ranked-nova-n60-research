"""VIA persistence stress test for the Nova QMK candidate (layer 2 only).

phase=write : back up layer 2, churn it until wear-leveling consolidates
              (erase path), restore it, then set marker slot [2,4,9].
phase=check : read layer 2 + marker and compare to the saved backup.
"""
import sys, json, time, struct
sys.path.insert(0, r"<LOCAL_USER>\rynked\.tools")
import hid

OUT = sys.argv[2]
PHASE = sys.argv[1]
ROWS, COLS, LAYER = 6, 11, 2
MARKER = (2, 4, 9)
MARKER_VALUE = 0x0005

dev = [d for d in hid.enumerate(0x3532, 0xA0A3) if d["usage_page"] == 0xFF60 and d["usage"] == 0x61]
assert len(dev) == 1, dev
h = hid.Device(path=dev[0]["path"])


def cmd(data):
    pkt = bytes(data).ljust(32, b"\0")
    assert h.write(b"\0" + pkt) == 33
    r = bytes(h.read(33, 2000))
    if len(r) == 33 and r[0] == 0:
        r = r[1:]
    assert len(r) == 32, r
    return r


def diag():
    r = cmd([2, 0x82])
    stage = r[3]
    flags, addr, page, perm, gate, status, word = struct.unpack_from("<7I", r, 4)
    return dict(stage=stage, flags=flags, addr=addr, page=page, gate=gate, status=status, word=word)


def get_key(l, row, col):
    return int.from_bytes(cmd([4, l, row, col])[4:6], "big")


def set_key(l, row, col, v):
    r = cmd([5, l, row, col, v >> 8, v & 255])
    assert int.from_bytes(r[4:6], "big") == v


def layer():
    return {(r, c): get_key(LAYER, r, c) for r in range(ROWS) for c in range(COLS)}


res = dict(phase=PHASE, protocol=cmd([1])[:3].hex(), diag_start=diag())
try:
    if PHASE == "write":
        orig = layer()
        res["backup"] = {f"{r},{c}": v for (r, c), v in orig.items()}
        trace, max_addr, consolidated = [], 0, False
        for rnd in range(40):
            for (r, c), v in orig.items():
                if (r, c) == MARKER[1:]:
                    continue
                set_key(LAYER, r, c, 0x0004 + ((rnd + r + c) % 20) if v != 0x0004 + ((rnd + r + c) % 20) else 0x0030)
                d = diag()
                if d["stage"] != 5:
                    trace.append(d)
                if d["addr"] < max_addr - 0x100:
                    consolidated = True
                max_addr = max(max_addr, d["addr"])
            res.setdefault("round_diag", []).append(diag())
            if consolidated and rnd >= 1:
                break
        res["consolidated"] = consolidated
        res["non_stage5"] = trace[:20]
        for (r, c), v in orig.items():
            if (r, c) != MARKER[1:]:
                set_key(LAYER, r, c, v)
        set_key(*MARKER, MARKER_VALUE)
        expect = dict(orig)
        expect[MARKER[1:]] = MARKER_VALUE
        now = layer()
        res["readback_ok"] = now == expect
        res["expected"] = {f"{r},{c}": v for (r, c), v in expect.items()}
    else:
        saved = json.load(open(sys.argv[3]))
        expect = {tuple(map(int, k.split(","))): v for k, v in saved["expected"].items()}
        now = layer()
        res["mismatch"] = {f"{r},{c}": [expect[(r, c)], now[(r, c)]] for (r, c) in expect if expect[(r, c)] != now[(r, c)]}
        res["persisted"] = not res["mismatch"]
    res["diag_end"] = diag()
finally:
    h.close()
    json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ("backup", "expected", "round_diag")}, indent=1))
print("rounds:", [ (d["stage"], hex(d["addr"])) for d in res.get("round_diag", [])])
