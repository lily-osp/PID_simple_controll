#!/usr/bin/env python3
"""Full-integration schematic rebuild for bldc_esp32_driver (JYQD-V7.3E3 architecture).

Real netlist built from stub wires + net labels; verified by kicad-cli netlist export.
"""
import re, random, uuid as uuidlib

SCH = "/home/azzar/project/microcontrollers/03_projects/pids/pid-simple-controll/PCB/bldc_esp32_driver/bldc_esp32_driver.kicad_sch"
KSYM = "/usr/share/kicad/symbols"

def rand_uuid():
    return str(uuidlib.uuid4())

def brace(text, start):
    d = 0
    for k in range(start, len(text)):
        if text[k] == '(': d += 1
        elif text[k] == ')':
            d -= 1
            if d == 0: return text[start:k+1], k+1
    raise ValueError("unbalanced")

# ---------------------------------------------------------------- load + extract
txt = open(SCH).read()
head_uuid = re.search(r'\(uuid "([^"]+)"\)', txt).group(1)
li = txt.find('(lib_symbols')
lib, _e = brace_block = brace(txt, li)

def extract_libTop(symfile, name):
    t = open(symfile).read()
    i = t.find(f'"{name}"'); assert i > 0, name
    s = t.rfind('(symbol ', 0, i)
    blk, _ = brace(t, s)
    return blk

l7805 = extract_libTop(f"{KSYM}/Regulator_Linear.kicad_sym", "L7805")
l7812 = extract_libTop(f"{KSYM}/Regulator_Linear.kicad_sym", "L7812")
conn6 = extract_libTop(f"{KSYM}/Connector_Generic.kicad_sym", "Conn_01x06")
conn2 = extract_libTop(f"{KSYM}/Connector_Generic.kicad_sym", "Conn_01x02")
conn3 = extract_libTop(f"{KSYM}/Connector_Generic.kicad_sym", "Conn_01x03")

def embed2(blk, libname):
    # rename only the TOP symbol (children keep suffix-only names, e.g. "X_1_1")
    def ren(m):
        n = m.group(1)
        return f'(symbol "{libname}:{n}"' if ':' not in n else m.group(0)
    return re.sub(r'\(symbol "([^"]+)"', ren, out := blk, count=1)

# sanitize cut: strip TODAY's-file leftovers from earlier generator passes:
#   duplicate defs of the dynamic symbols + stale lib-prefix on their children
DYN = [("L7805", "Regulator_Linear:L7805"), ("L7812", "Regulator_Linear:L7812"),
       ("Conn6", "Connector_Generic:Conn_01x06"),
       ("Conn2", "Connector_Generic:Conn_01x02"),
       ("Conn3", "Connector_Generic:Conn_01x03")]
for _nm, _pfx in DYN:
    while True:
        _i = lib.find(f'(symbol "{_pfx}"')
        if _i < 0:
            break
        _blk, _e = brace(lib, _i)
        lib = lib[:_i] + lib[_e:]
for _pre in ["Regulator_Linear:L7805_", "Regulator_Linear:L7812_1_", "Connector_Generic:Conn_01x06_",
             "Connector_Generic:Conn_01x02_", "Connector_Generic:Conn_01x03_"]:
    lib = lib.replace(f'(symbol "{_pre}', '(symbol "')

# L7812 has no child of its own (extends L7805) -> synthesize explicit child body
l7812 = re.sub(r'\(extends "L7805"\)\s*', '', l7812)
ic = l7805.find('(symbol "L7805_1_1"')
cb, _ = brace(l7805, ic)
nc = '(symbol "L7812_1_1"' + cb[len('(symbol "L7805_1_1"'):]
l7812 = l7812[:-1] + nc + ')'

l7805b = embed2(l7805, "Regulator_Linear")
l7812b = embed2(l7812, "Regulator_Linear")
conn6b = embed2(conn6, "Connector_Generic")
conn2b = embed2(conn2, "Connector_Generic")
conn3b = embed2(conn3, "Connector_Generic")
lib = lib[:-1] + "\n" + l7805b + "\n" + l7812b + "\n" + conn6b + "\n" + conn2b + "\n" + conn3b + "\n  )"

# JY213L top pins 20/19/18 all sit at x=0 (same column) with upward stubs -> spread
# horizontally so their up-wires don't collide (netlist neutrality: only pin x moves)
_ji = lib.find('(symbol "cameflex:JY213L"')
_jb, _je = brace(lib, _ji)
_jb = _jb.replace('(at 0 17.78 270)', '(at -2.54 17.78 270)')
_jb = _jb.replace('(at 0 12.7 270)', '(at 2.54 12.7 270)')
lib = lib[:_ji] + _jb + lib[_je:]

# ---------------------------------------------------------------- WEMOS rewrite (pin numbers = physical pads)
l_names = ["GPIO5","GPIO6","GPIO7","GPIO8","GPIO9","GPIO10","GPIO20","GPIO21"]
r_names = ["GPIO0","GPIO1","GPIO2","GPIO3","GPIO4","3V3","GND","5V"]
pnt = {n: ("power_out" if n=="3V3" else "power_in" if n=="GND" else "bidirectional") for n in l_names+r_names}
wemos_pins = ""
for i,n in enumerate(l_names):
    y = 8.89 - i*2.54
    wemos_pins += f'(pin {pnt[n]} line (at -10.16 {y:.2f} 0) (length 2.54)\n\t(name "{n}" (effects (font (size 1.27 1.27))))\n\t(number "{i+1}" (effects (font (size 1.27 1.27)))))\n'
for i,n in enumerate(r_names):
    y = 8.89 - i*2.54
    wemos_pins += f'(pin {pnt[n]} line (at 10.16 {y:.2f} 180) (length 2.54)\n\t(name "{n}" (effects (font (size 1.27 1.27))))\n\t(number "{i+9}" (effects (font (size 1.27 1.27)))))\n'
wemos_sym = f'''(symbol "RF_Module:WEMOS_C3_mini" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)
    (property "Reference" "U" (at 0 14.605 0) (effects (font (size 1.27 1.27))))
    (property "Value" "WEMOS_C3_mini" (at 0 -14.605 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Datasheet" "https://www.wemos.cc/en/latest/c3/c3_mini.html" (at 0 0 0) (hide yes))
    (symbol "WEMOS_C3_mini_1_1"
        (rectangle (start -11.43 11.43) (end 11.43 -11.43) (stroke (width 0.254) (type default)) (fill (type background)))
        (text "ESP32-C3 SuperMini" (at 0 11.43 0) (effects (font (size 1.27 1.27))))
{wemos_pins}    )
)'''
s = lib.find('(symbol "RF_Module:WEMOS_C3_mini"'); assert s>0
wblk, we = brace(lib, s)
lib = lib[:s] + wemos_sym + lib[we:]

# ---------------------------------------------------------------- pin parsing
def parse_pins(unit_name):
    i = lib.find(f'(symbol "{unit_name}"')
    assert i > 0, unit_name
    blk, _ = brace(lib, i)
    pins = {}
    for m in re.finditer(r'\(pin\b', blk):
        b, _ = brace(blk, m.start())
        num = re.search(r'\(number "([^"]+)"', b)
        nm = re.search(r'\(name "([^"]*)"', b)
        at = re.search(r'\(at ([-\d.]+) ([-\d.]+) (\d+)\)', b)
        if not (num and at): continue
        pins[num.group(1)] = {"name": nm.group(1) if nm else num.group(1),
                              "x": float(at.group(1)), "y": float(at.group(2)),
                              "rot": int(at.group(3)),
                              "type": re.search(r'^\(pin (\w+)', b).group(1)}
    return pins

PINS = {}
def parse_pins_merged(unit_name):
    pins = parse_pins(unit_name)
    if not pins and unit_name.endswith("_1"):
        # legacy embedded style: pins stored in _N_0 body
        pins = parse_pins(unit_name[:-2] + "_0")
    return pins

def P(libid, unit, unit_name):
    PINS[(libid, unit)] = parse_pins_merged(unit_name)

P("cameflex:JY01", 1, "JY01_1_1")
P("cameflex:JY213L", 1, "JY213L_1_1")
P("cameflex:JY2605M_DualNMOS", 1, "JY2605M_DualNMOS_1_1")
P("RF_Module:WEMOS_C3_mini", 1, "WEMOS_C3_mini_1_1")
P("Transistor_FET:CSD13380F3", 1, "CSD13380F3_1_1")
P("Regulator_Linear:L7805", 1, "L7805_1_1")
# L7812 extends L7805 -> same pins (1=IN, 2=GND, 3=OUT)
P("Regulator_Linear:L7812", 1, "L7812_1_1")
P("Amplifier_Operational:LM324", 1, "LM324_1_1")
P("Amplifier_Operational:LM324", 2, "LM324_2_1")
P("Amplifier_Operational:LM324", 3, "LM324_3_1")
P("Amplifier_Operational:LM324", 4, "LM324_4_1")
P("Amplifier_Operational:LM324", 5, "LM324_5_1")
P("74xx:74HC14", 1, "74HC14_1_1")
P("74xx:74HC14", 2, "74HC14_2_1")
P("74xx:74HC14", 3, "74HC14_3_1")
P("74xx:74HC14", 4, "74HC14_4_1")
P("74xx:74HC14", 5, "74HC14_5_1")
P("74xx:74HC14", 6, "74HC14_6_1")
P("74xx:74HC14", 7, "74HC14_7_1")
P("Device:R_US", 1, "R_US_1_1")
P("Device:C", 1, "C_1_1")
P("Device:C_Polarized", 1, "C_Polarized_1_1")
P("Device:D", 1, "D_1_1")
P("Device:LED", 1, "LED_1_1")
P("Device:R_Potentiometer_US", 1, "R_Potentiometer_US_1_1")
P("Connector_Generic:Conn_01x05_Pin", 1, "Conn_01x05_Pin_1_1")
P("Connector_Generic:Conn_01x06", 1, "Conn_01x06_1_1")
P("Connector_Generic:Conn_01x09_Pin", 1, "Conn_01x09_Pin_1_1")
P("Connector_Generic:Conn_01x02", 1, "Conn_01x02_1_1")
P("Connector_Generic:Conn_01x03", 1, "Conn_01x03_1_1")

print("pin def check:")
for (a, b), ps in PINS.items():
    print(f'  {a} u{b}: {len(ps)} pins')

# (tail appended to gen_head.py)
# instance: (ref, lib_id, unit, value, footprint, x, y)
COMPS = [
    # --- power entry / bulk / regulators ---
    ("J5",  "Connector_Generic:Conn_01x02", 1, "P+,P-",  "TerminalBlock:TerminalBlock_MaiXu_MX126-5.0-02P_1x02_P5.00mm", 27.94, 60.96),
    ("J6",  "Connector_Generic:Conn_01x03", 1, "MA,MB,MC",  "TerminalBlock:TerminalBlock_MaiXu_MX126-5.0-03P_1x03_P5.00mm", 27.94, 76.2),
    ("C1",  "Device:C_Polarized", 1, "480uF/63V",  "Capacitor_THT:CP_Radial_D13.0mm_P5.00mm", 43.18, 63.5),
    ("C2",  "Device:C_Polarized", 1, "480uF/63V",  "Capacitor_THT:CP_Radial_D13.0mm_P5.00mm", 43.18, 78.74),
    ("C5",  "Device:C_Polarized", 1, "220uF/50V",  "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", 43.18, 93.98),
    ("U8",  "Regulator_Linear:L7812", 1, "7812", "Package_TO_SOT_THT:TO-220-3_Vertical", 60.96, 68.58),
    ("C3",  "Device:C_Polarized", 1, "220uF/50V",  "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", 76.2, 66.04),
    ("U7",  "Regulator_Linear:L7805", 1, "7805", "Package_TO_SOT_THT:TO-220-3_Vertical", 60.96, 83.82),
    ("C4",  "Device:C_Polarized", 1, "220uF/50V",  "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", 76.2, 81.28),
    # --- current shunt + Is filter ---
    ("R1",  "Device:R_US", 1, "R005_2512", "Resistor_SMD:R_2512_6332Metric", 33.02, 55.88),
    ("R36", "Device:R_US", 1, "1k", "Resistor_SMD:R_0805_2012Metric", 40.64, 52.07),
    ("C21", "Device:C", 1, "10nF", "Capacitor_SMD:C_0805_2012Metric", 48.26, 52.07),
    # --- controller IC + gate resistors in ---
    ("U1",  "cameflex:JY01", 1, "JY01(8559)", "Package_SO:SOP-16_3.9x9.9mm_P1.27mm", 124.46, 78.74),
    ("R8",  "Device:R_US", 1, "100R", "Resistor_SMD:R_0805_2012Metric", 146.05, 60.96),
    ("R9",  "Device:R_US", 1, "100R", "Resistor_SMD:R_0805_2012Metric", 146.05, 76.2),
    ("R10", "Device:R_US", 1, "100R", "Resistor_SMD:R_0805_2012Metric", 146.05, 91.44),
    ("R11", "Device:R_US", 1, "100R", "Resistor_SMD:R_0805_2012Metric", 146.05, 106.68),
    ("R12", "Device:R_US", 1, "100R", "Resistor_SMD:R_0805_2012Metric", 146.05, 121.92),
    ("R13", "Device:R_US", 1, "100R", "Resistor_SMD:R_0805_2012Metric", 146.05, 137.16),
    ("C11", "Device:C", 1, "100nF", "Capacitor_SMD:C_0805_2012Metric", 149.86, 50.8),
    ("C12", "Device:C", 1, "10uF", "Capacitor_SMD:C_0805_2012Metric", 158.75, 50.8),
    # --- 3-phase gate driver ---
    ("U3",  "cameflex:JY213L", 1, "JY213L", "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm", 165.1, 78.74),
    # --- bootstrap diodes + caps ---
    ("D1",  "Device:D", 1, "1N4148", "Diode_SMD:D_SOD-123", 165.1, 104.14),
    ("D2",  "Device:D", 1, "1N4148", "Diode_SMD:D_SOD-123", 177.8, 104.14),
    ("D3",  "Device:D", 1, "1N4148", "Diode_SMD:D_SOD-123", 190.5, 104.14),
    ("C13", "Device:C", 1, "10uF/25V", "Capacitor_SMD:C_0805_2012Metric", 165.1, 116.84),
    ("C14", "Device:C", 1, "10uF/25V", "Capacitor_SMD:C_0805_2012Metric", 177.8, 116.84),
    ("C15", "Device:C", 1, "10uF/25V", "Capacitor_SMD:C_0805_2012Metric", 203.2, 116.84),
    # --- driver-out gate resistors ---
    ("R14", "Device:R_US", 1, "15R", "Resistor_SMD:R_0805_2012Metric", 190.5, 60.96),
    ("R15", "Device:R_US", 1, "15R", "Resistor_SMD:R_0805_2012Metric", 190.5, 76.2),
    ("R16", "Device:R_US", 1, "15R", "Resistor_SMD:R_0805_2012Metric", 190.5, 91.44),
    ("R17", "Device:R_US", 1, "15R", "Resistor_SMD:R_0805_2012Metric", 190.5, 106.68),
    ("R18", "Device:R_US", 1, "15R", "Resistor_SMD:R_0805_2012Metric", 190.5, 121.92),
    ("R19", "Device:R_US", 1, "15R", "Resistor_SMD:R_0805_2012Metric", 190.5, 137.16),
    # --- half-bridges ---
    ("Q2",  "cameflex:JY2605M_DualNMOS", 1, "JY2605", "local:JY2605M_DFN8_5x6", 210.82, 55.88),
    ("Q3",  "cameflex:JY2605M_DualNMOS", 1, "JY2605", "local:JY2605M_DFN8_5x6", 210.82, 76.2),
    ("Q4",  "cameflex:JY2605M_DualNMOS", 1, "JY2605", "local:JY2605M_DFN8_5x6", 210.82, 96.52),
    # --- hall amp: connectors, ICs, passives ---
    ("J3",  "Connector_Generic:Conn_01x05_Pin", 1, "GND,Hc,Hb,Ha,5V", "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical", 25.4, 124.46),
    ("R21", "Device:R_US", 1, "10k", "Resistor_SMD:R_0805_2012Metric", 41.91, 124.46),
    ("R22", "Device:R_US", 1, "10k", "Resistor_SMD:R_0805_2012Metric", 41.91, 139.7),
    ("R23", "Device:R_US", 1, "10k", "Resistor_SMD:R_0805_2012Metric", 41.91, 154.94),
    ("C16", "Device:C", 1, "100nF", "Capacitor_SMD:C_0805_2012Metric", 50.8, 129.54),
    ("C17", "Device:C", 1, "100nF", "Capacitor_SMD:C_0805_2012Metric", 50.8, 144.78),
    ("C18", "Device:C", 1, "100nF", "Capacitor_SMD:C_0805_2012Metric", 50.8, 160.02),
    ("U4",  "Amplifier_Operational:LM324", 1, "LM324", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", 63.5, 124.46),
    ("U4",  "Amplifier_Operational:LM324", 2, "LM324", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", 63.5, 139.7),
    ("U4",  "Amplifier_Operational:LM324", 3, "LM324", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", 63.5, 154.94),
    ("U4",  "Amplifier_Operational:LM324", 4, "LM324", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", 154.94, 175.26),
    ("U4",  "Amplifier_Operational:LM324", 5, "LM324", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", 77.47, 111.76),
    ("R25", "Device:R_US", 1, "10k", "Resistor_SMD:R_0805_2012Metric", 86.36, 124.46),
    ("R26", "Device:R_US", 1, "10k", "Resistor_SMD:R_0805_2012Metric", 86.36, 139.7),
    ("R27", "Device:R_US", 1, "10k", "Resistor_SMD:R_0805_2012Metric", 86.36, 154.94),
    ("R29", "Device:R_US", 1, "1k", "Resistor_SMD:R_0805_2012Metric", 93.98, 124.46),
    ("R30", "Device:R_US", 1, "1k", "Resistor_SMD:R_0805_2012Metric", 93.98, 139.7),
    ("R31", "Device:R_US", 1, "1k", "Resistor_SMD:R_0805_2012Metric", 93.98, 154.94),
    ("U5",  "74xx:74HC14", 1, "74HC14", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", 106.68, 124.46),
    ("U5",  "74xx:74HC14", 2, "74HC14", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", 106.68, 139.7),
    ("U5",  "74xx:74HC14", 3, "74HC14", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", 106.68, 154.94),
    ("U5",  "74xx:74HC14", 4, "74HC14", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", 116.84, 175.26),
    ("U5",  "74xx:74HC14", 5, "74HC14", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", 137.16, 175.26),
    ("U5",  "74xx:74HC14", 6, "74HC14", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", 157.48, 167.64),
    ("U5",  "74xx:74HC14", 7, "74HC14", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", 121.92, 111.76),
    ("C19", "Device:C", 1, "100nF", "Capacitor_SMD:C_0805_2012Metric", 116.84, 114.3),
    ("C20", "Device:C", 1, "100nF", "Capacitor_SMD:C_0805_2012Metric", 124.46, 114.3),
    # --- control side ---
    ("U6",  "RF_Module:WEMOS_C3_mini", 1, "ESP32-C3-SuperMini", "local:ESP32-C3-SuperMini", 165.1, 208.28),
    ("U2",  "Transistor_FET:CSD13380F3", 1, "CSD13380F3", "Package_TO_SOT_SMD:SOT-23-3", 129.54, 220.98),
    ("R7",  "Device:R_US", 1, "100R", "Resistor_SMD:R_0805_2012Metric", 139.7, 210.82),
    ("R6",  "Device:R_US", 1, "10k", "Resistor_SMD:R_0805_2012Metric", 121.92, 195.58),
    ("R4",  "Device:R_US", 1, "2.2k", "Resistor_SMD:R_0805_2012Metric", 116.84, 187.96),
    ("R5",  "Device:R_US", 1, "3.3k", "Resistor_SMD:R_0805_2012Metric", 124.46, 187.96),
    ("C6",  "Device:C", 1, "100nF", "Capacitor_SMD:C_0805_2012Metric", 132.08, 187.96),
    ("RV1", "Device:R_Potentiometer_US", 1, "10K", "Potentiometer_THT:Potentiometer_Bourns_3296W_Vertical", 96.52, 198.12),
    ("R20", "Device:R_US", 1, "560R", "Resistor_SMD:R_0805_2012Metric", 111.76, 218.44),
    ("LED1", "Device:LED", 1, "PWR", "LED_SMD:LED_0805_2012Metric", 119.38, 218.44),
    ("R32", "Device:R_US", 1, "560R", "Resistor_SMD:R_0805_2012Metric", 139.7, 226.06),
    ("LED2", "Device:LED", 1, "ERR", "LED_SMD:LED_0805_2012Metric", 148.59, 218.44),
    ("R33", "Device:R_US", 1, "10k", "Resistor_SMD:R_0805_2012Metric", 41.91, 185.42),
    ("R34", "Device:R_US", 1, "1k", "Resistor_SMD:R_0805_2012Metric", 48.26, 193.04),
    ("R35", "Device:R_US", 1, "10k", "Resistor_SMD:R_0805_2012Metric", 41.91, 199.39),
]

# net table: netname -> [(ref, pin_number)]
NETS = {
    # ---- power ----
    "V_IN":  [("J5","1"), ("C1","1"), ("C2","1"), ("C5","1"), ("U8","1"), ("Q2","2"), ("Q2","8"), ("Q3","2"), ("Q3","8"), ("Q4","2"), ("Q4","8")],
    "PNEG":  [("J5","2"), ("R1","1"), ("R36","2")],
    "GND":   [("R1","2"), ("C1","2"), ("C2","2"), ("C5","2"), ("C3","2"), ("C4","2"),
              ("U8","2"), ("U7","2"), ("U3","8"), ("Q2","6"), ("Q3","6"), ("Q4","6"),
              ("U1","3"), ("U6","15"), ("U4","11"), ("U5","7"),
              ("R29","2"), ("R30","2"), ("R31","2"), ("R5","2"), ("C6","2"),
              ("LED1","1"), ("LED2","1"), ("U2","2"),
              ("C16","2"), ("C17","2"), ("C18","2"), ("C21","2"), ("C19","2"), ("C20","2"),
              ("C11","2"), ("C12","2"),
              ("U4","12"), ("U5","9"), ("U5","11"), ("U5","13"),
              ("J3","1"), ("RV1","3")],
    "ISENSE_F": [("U1","2"), ("R36","1"), ("C21","1")],
    "+12V":  [("U8","3"), ("U7","1"), ("C3","1"), ("C11","1"), ("C12","1"), ("U3","7"), ("D1","2"), ("D2","2"), ("D3","2")],
    "+5V":   [("U7","3"), ("C4","1"), ("U1","4"), ("U4","4"), ("U5","14"), ("U6","16"),
              ("J3","5"), ("R20","1"), ("R6","2"), ("R33","2"), ("R35","2"),
              ("C19","1"), ("C20","1")],
    "+3.3V": [("U6","14"), ("RV1","1")],
    # ---- phases ----
    "PH_A":  [("Q2","3"), ("Q2","5"), ("Q2","7"), ("U3","18"), ("C13","2"), ("J6","1")],
    "PH_B":  [("Q3","3"), ("Q3","5"), ("Q3","7"), ("U3","15"), ("C14","2"), ("J6","2")],
    "PH_C":  [("Q4","3"), ("Q4","5"), ("Q4","7"), ("U3","12"), ("C15","2"), ("J6","3")],
    # ---- bootstrap: anode->VB? no: anode=pin2(A)->+12V, cathode=pin1(K)->VB ----
    "VB_A":  [("U3","20"), ("D1","1"), ("C13","1")],
    "VB_B":  [("U3","17"), ("D2","1"), ("C14","1")],
    "VB_C":  [("U3","14"), ("D3","1"), ("C15","1")],
    # ---- gate chains (2-pin nets) ----
    "GO_AT":  [("U1","7"), ("R8","1")],
    "GI_HIN1":[("R8","2"), ("U3","1")],
    "GO_AB":  [("U1","8"), ("R9","1")],
    "GI_LIN1":[("R9","2"), ("U3","4")],
    "GO_BT":  [("U1","10"), ("R10","1")],
    "GI_HIN2":[("R10","2"), ("U3","2")],
    "GO_BB":  [("U1","9"), ("R11","1")],
    "GI_LIN2":[("R11","2"), ("U3","5")],
    "GO_CT":  [("U1","12"), ("R12","1")],
    "GI_HIN3":[("R12","2"), ("U3","3")],
    "GO_CB":  [("U1","11"), ("R13","1")],
    "GI_LIN3":[("R13","2"), ("U3","6")],
    "GP_HO1": [("U3","19"), ("R14","1")],
    "GQ_GH1": [("R14","2"), ("Q2","1")],
    "GP_LO1": [("U3","11"), ("R15","1")],
    "GQ_GL1": [("R15","2"), ("Q2","4")],
    "GP_HO2": [("U3","16"), ("R16","1")],
    "GQ_GH2": [("R16","2"), ("Q3","1")],
    "GP_LO2": [("U3","10"), ("R17","1")],
    "GQ_GL2": [("R17","2"), ("Q3","4")],
    "GP_HO3": [("U3","13"), ("R18","1")],
    "GQ_GH3": [("R18","2"), ("Q4","1")],
    "GP_LO3": [("U3","9"), ("R19","1")],
    "GQ_GL3": [("R19","2"), ("Q4","4")],
    # ---- hall amp chains: in -> RC filter -> gain(+11) -> schmitt ----
    "HB_IN_A": [("J3","4"), ("R21","1")],
    "HB_F_A":  [("R21","2"), ("C16","1"), ("U4","3")],
    "HB_M_A":  [("U4","2"), ("R25","2"), ("R29","1")],
    "HB_O_A":  [("U4","1"), ("R25","1"), ("U5","1")],
    "HB_IN_B": [("J3","3"), ("R22","1")],
    "HB_F_B":  [("R22","2"), ("C17","1"), ("U4","5")],
    "HB_M_B":  [("U4","6"), ("R26","2"), ("R30","1")],
    "HB_O_B":  [("U4","7"), ("R26","1"), ("U5","3")],
    "HB_IN_C": [("J3","2"), ("R23","1")],
    "HB_F_C":  [("R23","2"), ("C18","1"), ("U4","10")],
    "HB_M_C":  [("U4","9"), ("R27","2"), ("R31","1")],
    "HB_O_C":  [("U4","8"), ("R27","1"), ("U5","5")],
    "HALL_OUT_A": [("U5","2"), ("U1","13")],
    "HALL_OUT_B": [("U5","4"), ("U1","14")],
    "HALL_OUT_C": [("U5","6"), ("U1","15")],
    # ---- control ----
    "VR":     [("U1","16"), ("U2","3"), ("R6","1")],
    "PWM_OUT":[("U6","10"), ("R7","1")],
    "PWM_G":  [("R7","2"), ("U2","1")],
    "FG":     [("U1","6"), ("R4","1")],
    "RPM_IN": [("R4","2"), ("R5","1"), ("C6","1"), ("U6","9")],
    "POT_ADC":[("RV1","2"), ("U6","11")],
    "GPIO4":  [("U6","13"), ("R34","1")],
    "EL":     [("U1","1"), ("R33","1"), ("R34","2")],
    "ZF":     [("U1","5"), ("R35","1")],
    "GPIO5":  [("U6","1"), ("R32","1")],
    "OPA4_FB":[("U4","13"), ("U4","14")],
    "LED1_A": [("R20","2"), ("LED1","2")],
    "LED2_A": [("R32","2"), ("LED2","2")],
}

# ---------------------------------------------------------------- 6. emit image
# collect pin->net lookup from NETS: also validate uniqueness per pin
pin_net = {}
dup = []
for net, members in NETS.items():
    for (ref, pin) in members:
        if not pin or not ref:
            continue
        k = (ref, pin)
        if k in pin_net: dup.append((k, pin_net[k], net))
        pin_net[k] = net
assert not dup, f"duplicate pin assignments: {dup}"

# sanity: every referenced pin exists in its symbol's pinmap
missing = []
for (ref, libid, unit, val, fp, x, y) in COMPS:
    pmap = PINS[(libid, unit)]
    for (rkey, pnum), net in [((r,p), n) for n, ms in NETS.items() for (r, p) in ms if (r, p) in pin_net]:
        pass
for (r, p), net in pin_net.items():
    hit = [c for c in COMPS if c[0] == r and p in PINS[(c[1], c[2])]]
    if not hit:
        missing.append((r, p, net))
if missing:
    raise SystemExit(f"pins not found on any placed symbol: {missing}")

def emit():
    out = []
    out.append(f'''(kicad_sch
	(version 20250114)
	(generator "eeschema")
	(generator_version "9.0")
	(uuid "{head_uuid}")
	(paper "A4")
	(title_block
		(title "BLDC ESP32-C3 Full-Integration Driver (JYQD-V7.3E3 architecture)")
		(date "2026-10-30")
		(rev "2")
		(company "pid-simple-controll")
	)
''')
    out.append(lib)
    out.append('\n')

    # stub wires + labels: adaptive grid stubs (each stub picks the shortest
    # multiple of 2.54 that stays clear of every other pin/wire/label point)
    segs = []      # (net, pin_sheet, tip, ref.pin, rot)
    pin_pts = {}   # (x,y) -> [(ref.pin, net_or_None)]
    for (ref, libid, unit, val, fp, x, y) in COMPS:
        pmap = PINS[(libid, unit)]
        for pnum, pinfo in pmap.items():
            ax = x + pinfo["x"]; ay = y - pinfo["y"]
            net = pin_net.get((ref, pnum))
            pin_pts.setdefault((ax, ay), []).append((f"{ref}.{pnum}", net))

    # pre-check: two labelled pins of different nets sitting on the same point
    for pt, owners in sorted(pin_pts.items()):
        if len(owners) > 1 and owners[0][1] != owners[1][1]:
            raise SystemExit(f"pin-pin coincidence, move components: {pt} {owners}")

    OWNER = {}
    for (x, y), owners in pin_pts.items():
        for rp, net in owners:
            OWNER[(x, y)] = net   # labeled wins; unlabeled overwritten if shared
    for (x, y), owners in pin_pts.items():
        if OWNER[(x, y)] is None:
            OWNER[(x, y)] = owners[0][1]

    def seg_contact(a, b, ax, ay, sx_or, sy_or):
        # a: existing segment tuple (net, (x1,y1), (x2,y2))
        # b: proposed (net2, (pin), (tip))
        n1, (x1, y1), (x2, y2) = a
        n2, (px, py), (tx, ty) = b
        if n1 == n2:
            return False
        def coinc(p, q): return abs(p[0]-q[0]) < 1e-6 and abs(p[1]-q[1]) < 1e-6
        for p in ((x1, y1), (x2, y2)):
            if coinc(p, (tx, ty)): return True
        if coinc((px, py), (x1, y1)) or coinc((px, py), (x2, y2)): return True
        # proposed tip on existing interior
        if abs(x1-x2) < 1e-6 and abs(tx-x1) < 1e-6 and min(y1, y2) <= ty <= max(y1, y2): return True
        if abs(y1-y2) < 1e-6 and abs(ty-y1) < 1e-6 and min(x1, x2) <= tx <= max(x1, x2): return True
        # existing endpoint on proposed interior
        for p in ((x1, y1), (x2, y2)):
            if abs(px - tx) < 1e-6 and abs(p[0]-px) < 1e-6 and min(py, ty) <= p[1] <= max(py, ty): return True
            if abs(py - ty) < 1e-6 and abs(p[1]-py) < 1e-6 and min(px, tx) <= p[0] <= max(px, tx): return True
        return False

    def blocked(tip, net, others, pts):
        # tip lands on some existing segment interior/endpoint or foreign pin point
        for rp, n in pts.get(tip, []):
            if n != net: return True
        for a in others:
            seg = a[0]
            n1, (x1, y1), (x2, y2) = seg
            if n1 == net: continue
            if abs(x1-x2) < 1e-6 and abs(tip[0]-x1) < 1e-6 and min(y1, y2) <= tip[1] <= max(y1, y2): return True
            if abs(y1-y2) < 1e-6 and abs(tip[1]-y1) < 1e-6 and min(x1, x2) <= tip[0] <= max(x1, x2): return True
        return False

    placed = []   # (seg, ax, ay, net, rp, rot)
    lengths = {}
    order = sorted(((x + pinfo["x"], y - pinfo["y"], rp)
                    for (ref, libid, unit, val, fp, x, y) in COMPS
                    for pnum, pinfo in PINS[(libid, unit)].items()
                    for rp in [f"{ref}.{pnum}"] if pin_net.get((ref, pnum))))
    # index pin info for ordered placement
    pin_loc = {}
    for (ref, libid, unit, val, fp, x, y) in COMPS:
        for pnum, pinfo in PINS[(libid, unit)].items():
            net = pin_net.get((ref, pnum))
            if net:
                pin_loc[f"{ref}.{pnum}"] = (x + pinfo["x"], y - pinfo["y"], pinfo["rot"], net)
    for _ox, _oy, rp in order:
        ax, ay, rot, net = pin_loc[rp]
        dirs = {0: (-1, 0), 90: (0, 1), 180: (1, 0), 270: (0, -1)}
        ux, uy = dirs[rot]
        chosen = None
        for step in range(1, 8):
            L = step * 2.54
            tip = (ax + ux * L, ay + uy * L)
            seg = (net, (ax, ay), tip)
            bad = False
            for (oseg, oax, oay, onet, orp, orot, otip) in placed:
                if seg_contact(oseg, (net, (ax, ay), tip), oax, oay, ax, ay):
                    bad = True; break
            if not bad:
                # proposed segment must not touch foreign pin points (incl. unlabeled)
                for (ptx, pty), owners in pin_pts.items():
                    foreign = any(n2 != net for rp2, n2 in owners)
                    if not foreign:
                        continue
                    if abs(tip[0]-ptx) < 1e-6 and abs(tip[1]-pty) < 1e-6:
                        bad = True; break
                    on_pin = False
                    if ux == 0 and abs(ptx - ax) < 1e-6 and min(ay, tip[1]) <= pty <= max(ay, tip[1]) and (ptx, pty) != (ax, ay):
                        on_pin = True
                    if uy == 0 and abs(pty - ay) < 1e-6 and min(ax, tip[0]) <= ptx <= max(ax, tip[0]) and (ptx, pty) != (ax, ay):
                        on_pin = True
                    if on_pin:
                        bad = True; break
            if bad: continue
            chosen = (seg, ax, ay, net, rp, rot, tip)
            break
        if chosen is None:
            raise SystemExit(f"no clear stub length for {rp} (net {net}) at ({ax},{ay}) rot{rot}")
        placed.append(chosen)
        lengths[rp] = (ux * chosen[6][2][0] if False else 0)
    # final tip coordinates
    used = set()
    for (seg, ax, ay, net, rp, rot, tip) in placed:
        ref, pnum = rp.split(".", 1)
        used.add((ref, pnum))
        sx, sy = tip
        out.append(f'(wire\n\t(pts (xy {ax:.2f} {ay:.2f}) (xy {sx:.2f} {sy:.2f}))\n\t(stroke (width 0) (type default))\n\t(uuid {rand_uuid()})\n)\n')
        out.append(f'''(label "{net}"
	(at {sx:.2f} {sy:.2f} 0)
	(fields_autoplaced yes)
	(effects (font (size 1.27 1.27)) (justify left bottom))
	(uuid {rand_uuid()})
)
''')

    # symbol instances
    symtxt = []
    for idx, (ref, libid, unit, val, fp, x, y) in enumerate(COMPS):
        uid = rand_uuid()
        pmap = PINS[(libid, unit)]
        pinout_blocks = "\n".join(f'\t\t(pin "{n}" (uuid {rand_uuid()}))' for n in pmap.keys())
        symtxt.append(f'''
	(symbol
		(lib_id "{libid}")
		(at {x:.2f} {y:.2f} 0)
		(unit {unit})
		(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
		(uuid {uid})
		(property "Reference" "{ref}" (at {x:.2f} {y - 3.5:.2f} 0)
			(show_name no) (do_not_autoplace yes)
			(effects (font (size 1.27 1.27))))
		(property "Value" "{val}" (at {x:.2f} {y + 3.5:.2f} 0)
			(do_not_autoplace yes)
			(effects (font (size 1.27 1.27))))
		(property "Footprint" "{fp}" (at {x:.2f} {y:.2f} 0)
			(effects (font (size 1.27 1.27)) (hide yes)))
		(property "Datasheet" "~" (at {x:.2f} {y:.2f} 0)
			(effects (font (size 1.27 1.27)) (hide yes)))
{pinout_blocks}
		(instances (project "bldc_esp32_driver"
			(path "/{head_uuid}"
				(reference "{ref}") (unit {unit})
			)
		))
	)
''')
    insts = "".join(symtxt)

    body = "".join(out[2:])
    tail = f'''{body}{insts}
	(sheet_instances
		(path "/"
			(page "1")
		)
	)
	(embedded_fonts no)
)
'''
    full = "".join(out[:2]) + tail
    open(SCH, "w").write(full)
    print(f"wrote {SCH}: {len(full)} bytes")
    print("labeled pins:", len(used), "of", sum(len(PINS[(c[1], c[2])]) for c in COMPS))

emit()
