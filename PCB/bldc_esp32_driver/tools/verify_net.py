#!/usr/bin/env python3
"""Verify exported netlist against the generator's NETS intent table."""
import re, importlib.util, sys
spec = importlib.util.spec_from_file_location("gen", "/tmp/opencode/gen_sch_full.py")
gen = importlib.util.module_from_spec(spec)
sys.modules["gen"] = gen
try:
    spec.loader.exec_module(gen)
except SystemExit:
    pass
NETS = gen.NETS

txt = open("/tmp/opencode/net_full.net").read()
blocks = txt.split('(net (code ')[1:]
actual = {}  # (ref, pin) -> net
for b in blocks:
    nm = re.search(r'\(name "([^"]+)"', b)
    nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"', b)
    if not nm:
        continue
    for r, p in nodes:
        k = (r, p)
        if k in actual:
            print(f"PIN IN TWO NETS: {k} {actual[k]} + {nm.group(1)}")
        actual[k] = nm.group(1)

OK = True
for net, members in sorted(NETS.items()):
    for ref, pin in members:
        if not pin or not ref:
            continue
        got = (actual.get((ref, pin)) or "").lstrip("/")
        if got != net:
            print(f"MISMATCH {ref}.{pin}: designed={net} actual={got}")
            OK = False
print("designed nets:", len(NETS), "pins designed:",
      sum(1 for n, ms in NETS.items() for r, p in ms if p and r))
print("VERDICT:", "PASS" if OK else "FAIL")
