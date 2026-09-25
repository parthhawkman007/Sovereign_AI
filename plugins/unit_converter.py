"""
Sovereign AI Workbench — Sample Plugin: Engineering Unit Converter
Demonstrates the plugin architecture. This module is auto-loaded by plugin_loader.py
at startup and its tools are made available to the agent.
"""

from langchain_core.tools import tool


@tool
def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """
    Converts engineering units on-device. 
    Supports: pressure (bar, psi, kPa, MPa, atm), 
    temperature (C, F, K), 
    flow (m3/h, L/min, GPM, SCFM),
    length (mm, cm, m, inch, ft),
    mass (kg, g, tonne, lb).
    Example: convert_units(1.0, 'bar', 'psi')
    """
    from_unit = from_unit.strip().lower()
    to_unit = to_unit.strip().lower()

    # ── Pressure (base: Pa) ──────────────────────────────────────────────────
    pressure = {
        'pa': 1.0, 'kpa': 1e3, 'mpa': 1e6, 'bar': 1e5,
        'psi': 6894.757, 'atm': 101325.0,
    }
    # ── Temperature (special-cased) ─────────────────────────────────────────
    temp_units = {'c', 'f', 'k', '°c', '°f'}

    # ── Flow (base: m3/s) ────────────────────────────────────────────────────
    flow = {
        'm3/h': 1/3600, 'm3/s': 1.0,
        'l/min': 1/60000, 'lpm': 1/60000,
        'gpm': 6.30902e-5,
        'scfm': 4.71947e-4,
    }
    # ── Length (base: m) ─────────────────────────────────────────────────────
    length = {
        'm': 1.0, 'cm': 0.01, 'mm': 0.001,
        'inch': 0.0254, 'in': 0.0254, 'ft': 0.3048,
    }
    # ── Mass (base: kg) ──────────────────────────────────────────────────────
    mass = {
        'kg': 1.0, 'g': 0.001, 'tonne': 1000.0,
        'lb': 0.453592, 'lbs': 0.453592,
    }

    def _conv(table: dict) -> str:
        if from_unit in table and to_unit in table:
            result = value * table[from_unit] / table[to_unit]
            return f"{value} {from_unit.upper()} = {result:.6g} {to_unit.upper()}"
        return None

    # Temperature special case
    if from_unit in temp_units or to_unit in temp_units:
        fu = from_unit.replace('°', '')
        tu = to_unit.replace('°', '')
        try:
            if fu == 'c' and tu == 'f':   result = value * 9/5 + 32
            elif fu == 'f' and tu == 'c': result = (value - 32) * 5/9
            elif fu == 'c' and tu == 'k': result = value + 273.15
            elif fu == 'k' and tu == 'c': result = value - 273.15
            elif fu == 'f' and tu == 'k': result = (value - 32) * 5/9 + 273.15
            elif fu == 'k' and tu == 'f': result = (value - 273.15) * 9/5 + 32
            elif fu == tu:                result = value
            else:
                return f"Unsupported temperature conversion: {from_unit} → {to_unit}"
            return f"{value} {fu.upper()} = {result:.6g} {tu.upper()}"
        except Exception as e:
            return f"Temperature conversion error: {e}"

    for table in (pressure, flow, length, mass):
        r = _conv(table)
        if r:
            return r

    return (
        f"Unsupported unit pair: '{from_unit}' → '{to_unit}'. "
        "Supported groups: pressure (Pa/kPa/MPa/bar/psi/atm), "
        "temperature (C/F/K), flow (m3/h/L/min/GPM/SCFM), "
        "length (mm/cm/m/inch/ft), mass (kg/g/tonne/lb)."
    )


# Plugin manifest — plugin_loader.py reads this to discover tools
PLUGIN_TOOLS = [convert_units]
PLUGIN_NAME = "Engineering Unit Converter"
PLUGIN_VERSION = "1.0"
PLUGIN_DESCRIPTION = "On-device unit conversion for industrial engineering quantities."
