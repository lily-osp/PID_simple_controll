#!/bin/bash
#
# Build all ATtiny85 firmware variants: v2, v3 and v4, each at 8 MHz and 16 MHz.
# Built with arduino-cli + ATTinyCore (the old damellis attiny:avr@1.0.2 core
# no longer compiles with the installed avr-gcc). Output: hex/ dir.
#
#   v2_8mhz.hex     v2_16mhz.hex     (Arduino core, integer PI)
#   v3_8mhz.hex     v3_16mhz.hex     (Arduino core + failsafe/anti-windup)
#   v4_8mhz.hex     v4_16mhz.hex     (deadband + oversampling, 1440 rpm)
#
# Fuses: 8 MHz -> lfuse 0xE2 (factory default, no PLL) -- RECOMMENDED
#        16 MHz PLL -> lfuse 0xE1 (requires PLL lock; use only if 8 MHz fails)
#   avrdude -c arduino -p attiny85 -P /dev/ttyACM0 -b 19200 -U lfuse:w:0xE2:m  # 8 MHz
#   avrdude -c arduino -p attiny85 -P /dev/ttyACM0 -b 19200 -U lfuse:w:0xE1:m  # 16 MHz

set -e
cd "$(dirname "$0")"

# Scrub host CFLAGS that break the AVR cross-compile (rtk wrapper leak).
unset C_INCLUDE_PATH CPLUS_INCLUDE_PATH CPATH CFLAGS CXXFLAGS

mkdir -p hex
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

FQBN8="ATTinyCore:avr:attinyx5:chip=85,clock=8internal"
FQBN16="ATTinyCore:avr:attinyx5:chip=85,clock=16pll"

build() {
    local sketch="$1" tag="$2" fqbn="$3"
    arduino-cli compile --fqbn "$fqbn" \
        --build-path "$BUILD_DIR/$tag" "$sketch" >/dev/null 2>&1
    cp "$BUILD_DIR/$tag/$(basename "$sketch").ino.hex" "hex/$tag.hex"
    local size
    size=$(stat -c%s "hex/$tag.hex")
    echo "  built hex/$tag.hex  ($size B, $fqbn)"
}

echo "Building all variants (ATTinyCore)..."
build v2 v2_8mhz "$FQBN8"
build v2 v2_16mhz "$FQBN16"
build v3 v3_8mhz "$FQBN8"
build v3 v3_16mhz "$FQBN16"
build v4 v4_8mhz "$FQBN8"
build v4 v4_16mhz "$FQBN16"
echo "Done."
