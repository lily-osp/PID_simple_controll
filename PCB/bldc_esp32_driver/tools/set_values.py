#!/usr/bin/env python3
"""Set schematic component values by reference.

Usage: set_values.py C13=1uF/50V C12=10uF/25V ...

Edits the Value property of each symbol *instance* (the lib_symbols cache is left
alone, which is what KiCad does when you change a value in the GUI).
"""
import re
import sys

SCH = "bldc_esp32_driver.kicad_sch"


def top_level_symbols(text):
    """Yield (start, end, block) for every symbol instance (direct child of root).

    The schematic root is (kicad_sch ...), so its children open at depth 1 and
    lib_symbols members open at depth 2.
    """
    depth, start, in_str = 0, None, False
    for i, ch in enumerate(text):
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "(":
            if depth == 1 and text.startswith("(symbol", i):
                start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 1 and start is not None:
                yield start, i + 1, text[start:i + 1]
                start = None


def main(pairs):
    wanted = dict(p.split("=", 1) for p in pairs)
    text = open(SCH).read()
    edits = []
    for start, end, block in top_level_symbols(text):
        m = re.search(r'\(reference "([^"]+)"\) \(unit 1\)', block)
        if not m or m.group(1) not in wanted:
            continue
        ref = m.group(1)
        vm = re.search(r'\(property "Value" "([^"]*)"', block)
        if not vm:
            print(f"  {ref}: no Value property, skipped")
            continue
        old = vm.group(1)
        new = wanted.pop(ref)
        if old == new:
            continue
        vstart, vend = start + vm.start(1), start + vm.end(1)
        edits.append((vstart, vend, new))
        print(f"  {ref}: {old} -> {new}")
    if wanted:
        sys.exit(f"not found in schematic: {', '.join(wanted)}")
    for vstart, vend, new in sorted(edits, reverse=True):
        text = text[:vstart] + new + text[vend:]
    open(SCH, "w").write(text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
