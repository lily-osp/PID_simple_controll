# Tech Stack — BLDC Motor PID Controller

## Overview

Brownfield embedded product. **Single target: ESP32-C3** (small form factor + maximum stability), deployed on the custom driver PCB. Former Arduino Uno / ATtiny85 variants were removed on 2026-10-31 (commit `396ade7`) and remain in git history.

## Languages

- **C/C++ (Arduino Wiring):** All firmware in `.ino` + shared `.h` modules (`pid_common.h`, `rpm_common.h`, `config_common.h`, `config.h`). Arduino IDE compatible, PlatformIO compatible.

## Microcontrollers & Hardware

| Target | MCU | Clock | Role | Form Factor |
|--------|-----|-------|------|-------------|
| ESP32-C3 `control/` (bench) | ESP32-C3 (RISC-V 32-bit, FPU) | 160 MHz | **Bring-up / service** (serial console, telemetry) | Module ~18×20 mm, ~60 mA |
| ESP32-C3 `embedded/` (production) | ESP32-C3 (RISC-V 32-bit, FPU) | 160 MHz | **Production — enclosure** (silent, autonomous, stall failsafe) | Module ~18×20 mm, ~60 mA |

- **Motor HW:** 3-phase BLDC + single Hall sensor + driver (PWM in). Hall → GPIO ISR (ESP32-C3) via PCNT/interval measurement; PWM → LEDC 5 kHz. 5 V Hall requires 2.2 kΩ/3.3 kΩ divider for ESP32-C3 3.3 V inputs.
- **Driver PCB:** `PCB/V1/` — full-integration 64 × 98 mm 4-layer board (JYQD-V7.3E3 architecture: JY01 + JY213L + JY2605M, ESP32-C3 Super Mini onboard, Hall amp RC → LM324 ×11 → 74HC14). Previous 70 × 120 mm 2-layer revision kept at tag `v1`.

## Frameworks & Libraries

- **Arduino Core:** `esp32:esp32` Espressif (ESP32-C3, `nologo_esp32c3_super_mini`).
- **ESP32-C3 specifics:** FreeRTOS (200 Hz PID task, highest priority), LEDC hardware PWM, IRAM-resident ISR, sliding-window + IIR filter. No wireless stack — the C3 is used bare-metal for compute.
- **Shared drivers:** `pcnt_driver.h`, `pid_common.h`, `rpm_common.h`, `ledc_driver.h` live in `control/` and are included by `embedded/` via `../control/` (one implementation).

## Build & Tooling

- **Build:** `arduino-cli compile -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/control` (bench) / `esp32-c3/embedded` (production).
- **Artifacts:** `compiled/` binaries + `DDMMYYYY_<repo>.zip` release.
- **PCB:** KiCad (`PCB/V1/bldc_esp32_driver.kicad_*`, custom footprints, `tools/gen_sch_full.py` / `gen_pcb.py` / `verify_net.py`, plus the 4-layer routing and test-point tooling).

## CI/CD

- **GitHub Actions** `.github/workflows/compile.yml`: `setup-arduino-cli@v1` → Espressif board index → `core install esp32:esp32` → compile `control` + `embedded` → list artifacts → memory usage check → ZIP + auto-release (retry on 502).
- **Triggers:** pushes to `main`/`master`, tags `v*.*.*`, PRs.

## Quality & Style

- `.clang-format` (project root), `.pre-commit-config.yaml` (linters/formatters), `CONTRIBUTING.md` guidelines.
- No JS/TS/Python runtime; docs built via `docs/_config.yml` (GitHub Pages).

## Design Priorities

1. **Small form factor first** — ESP32-C3 Super Mini on the custom driver PCB.
2. **Stability at 1440 RPM** — 200 Hz deterministic loop + arming/soft-start/stall failsafe.
3. **One shared implementation** — drivers and control maths live in `control/` only; `embedded/` consumes them unchanged.
