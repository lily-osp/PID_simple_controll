# Track: PID Runtime Stability — intermittent start, slow warmup, overspeed

- **ID:** `pid-stability_20260830`
- **Type:** bug
- **Status:** new
- **Platforms:** ATtiny85 v1/v2/v3, ESP32-C3 control / control_ble
- **Success metric:** 100% start reliability (10/10 cold starts @1440 RPM)

## Artifacts

- [Specification](./spec.md)
- [Implementation Plan](./plan.md)
- [Metadata](./metadata.json)

## Evidence

- `evidence/` — cold-start traces, `verify_start.py` output, CI logs (to be added during implementation)

## Registry

- Entry in [Tracks Registry](../../tracks.md)
