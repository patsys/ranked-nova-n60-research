# Contributing

Please keep evidence and claims traceable. A change to a finding should link to a reproducible script, raw observation, or validation record and state whether it is offline, emulated, or physical. Preserve failed experiments and superseded interpretations in the timeline rather than silently removing them.

Do not add SQLite databases, credentials, virtual environments, or generated build trees. Do not describe persistent VIA as working until both cold-power replay and a fresh raw-flash read verify the same test value. Hardware-write changes must remain bounded and include an independent backup and post-write verification.
