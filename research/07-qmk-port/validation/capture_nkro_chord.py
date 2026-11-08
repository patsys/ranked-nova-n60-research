"""Observe only the eight explicitly requested test keys for up to three minutes.

Windows host-event verification; no HID writes, general key logger or text capture.
Physical German A S D F J K L O-umlaut produce Neo2 U I A E N R T D.
The result records maximum simultaneous count, target coverage and release only.
"""
import ctypes
import json
from pathlib import Path
import time

keys = 'UIAENRTD'
get_state = ctypes.windll.user32.GetAsyncKeyState
get_state.argtypes = [ctypes.c_int]
get_state.restype = ctypes.c_short
maximum = 0
coverage = set()
all_seen = False
released_after_all = False
deadline = time.monotonic() + 180
print('Eight-key test active for up to three minutes; ends after chord release. No text is recorded.', flush=True)
while time.monotonic() < deadline:
    down = {key for key in keys if get_state(ord(key)) & 0x8000}
    maximum = max(maximum, len(down))
    coverage.update(down)
    all_seen |= len(down) == 8
    if all_seen and not down:
        released_after_all = True
        break
    time.sleep(0.01)
result = dict(maximum_simultaneous_target_keys=maximum,
    all_target_keys_observed=len(coverage) == 8,
    all_eight_simultaneous=all_seen,
    all_released_after_chord=released_after_all,
    limitation='Windows aggregate key state; other keyboards must remain untouched. Proves the tested chord only.')
(Path(__file__).parent/'nkro_physical_chord_validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result), flush=True)
