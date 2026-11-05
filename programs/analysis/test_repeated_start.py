"""Check whether fresh START probes can execute in one HID session."""
import json
from pathlib import Path
from timing_channel import Channel,probe

calibrations={v:probe('cal',v) for v in [0,8]}
log=dict(exchanges=[])
channel=Channel()
try:
    channel.open()
    log['version']=channel.version
    for value in [0,8,0,8]:
        blob,spec=calibrations[value]
        record=dict(spec=spec,**channel.send(blob))
        log['exchanges'].append(record)
        Path('repeated_start_live.json').write_text(json.dumps(log,indent=2))
        print(json.dumps(record),flush=True)
    t=[r['post_write_ms'] for r in log['exchanges']]
    log['fresh_code_executed_on_repeated_START']=(t[1]-t[0]>100 and t[3]-t[2]>100 and abs(t[1]-t[3])<5 and abs(t[0]-t[2])<5)
    assert log['fresh_code_executed_on_repeated_START'],t
except Exception as error:
    log['error']=str(error)
    log['fresh_code_executed_on_repeated_START']=False
    raise
finally:
    log['final_state']=channel.close()
    Path('repeated_start_live.json').write_text(json.dumps(log,indent=2))
