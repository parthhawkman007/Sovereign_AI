# -*- coding: utf-8 -*-
import ast
import re
import math

try:
    import sympy
    from sympy.parsing.sympy_parser import parse_expr
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False


_UNIT_EQUIVALENCES = {
    'kw':  [('w', 1000)],
    'w':   [('kw', 0.001)],
    'mw':  [('w', 1e6), ('kw', 1000)],
    'kpa': [('pa', 1000), ('bar', 0.01), ('psi', 0.14504)],
    'mpa': [('pa', 1e6), ('bar', 10), ('psi', 145.038)],
    'bar': [('pa', 1e5), ('kpa', 100), ('psi', 14.5038)],
    'psi': [('pa', 6894.757), ('kpa', 6.895), ('bar', 0.06895)],
    'm3/h': [('l/min', 16.6667), ('gpm', 4.40287)],
    'l/min': [('m3/h', 0.06), ('gpm', 0.26417)],
    'mm':  [('m', 0.001), ('cm', 0.1)],
    'cm':  [('m', 0.01), ('mm', 10)],
    'km':  [('m', 1000)],
    'm':   [('mm', 1000), ('cm', 100), ('km', 0.001)],
    'kg':  [('g', 1000), ('tonne', 0.001), ('lb', 2.20462)],
    'g':   [('kg', 0.001)],
    'tonne': [('kg', 1000)],
    'lb':  [('kg', 0.453592)],
}

def _are_equivalent_units(r_val: float, r_unit: str,
                           d_val: float, d_unit: str,
                           tol: float = 0.01) -> bool:
    ru = r_unit.lower().strip()
    du = d_unit.lower().strip()
    if ru == du:
        return abs(r_val - d_val) / max(abs(d_val), 1e-9) < tol
    for target_unit, factor in _UNIT_EQUIVALENCES.get(ru, []):
        if target_unit == du:
            converted = r_val * factor
            return abs(converted - d_val) / max(abs(d_val), 1e-9) < tol
    for target_unit, factor in _UNIT_EQUIVALENCES.get(du, []):
        if target_unit == ru:
            converted = d_val * factor
            return abs(r_val - converted) / max(abs(r_val), 1e-9) < tol
    return False

class CalculationVerifier:
    def __init__(self):
        self.known_formulas = {
            frozenset(['pressure', 'radius', 'thickness']): ['pressure*radius/thickness', '(pressure*radius)/thickness'],
            frozenset(['force', 'area']): ['force/area'],
            frozenset(['mass', 'acceleration']): ['mass*acceleration', 'acceleration*mass'],
            frozenset(['stress', 'force', 'area']): ['force/area'],
            frozenset(['strain', 'delta_l', 'l']): ['delta_l/l'],
            frozenset(['young_modulus', 'stress', 'strain']): ['stress/strain'],
            frozenset(['torque', 'force', 'radius']): ['force*radius', 'radius*force'],
            frozenset(['moment', 'force', 'distance']): ['force*distance', 'distance*force'],
            frozenset(['work', 'force', 'distance']): ['force*distance'],
            frozenset(['power', 'work', 'time']): ['work/time'],
            frozenset(['velocity', 'distance', 'time']): ['distance/time'],
            frozenset(['acceleration', 'velocity', 'time']): ['velocity/time'],
            frozenset(['density', 'mass', 'volume']): ['mass/volume'],
            frozenset(['voltage', 'current']): ['voltage*current', 'current*voltage'],
            frozenset(['voltage', 'resistance']): ['voltage/resistance'],
            frozenset(['current', 'resistance']): ['current*resistance', 'resistance*current', 'current**2*resistance'],
            frozenset(['power', 'voltage', 'current']): ['voltage*current', 'current*voltage'],
            frozenset(['power', 'current', 'resistance']): ['current**2*resistance'],
            frozenset(['power', 'voltage', 'current', 'power_factor']): [
                '3**0.5*voltage*current*power_factor',
                'voltage*current*power_factor*3**0.5',
                'math.sqrt(3)*voltage*current*power_factor',
                'voltage*current*power_factor*math.sqrt(3)',
                '1.732*voltage*current*power_factor',
                'voltage*current*power_factor*1.732',
            ],
            frozenset(['power', 'voltage', 'current', 'pf']): [
                '3**0.5*voltage*current*pf',
                'voltage*current*pf*3**0.5',
                'math.sqrt(3)*voltage*current*pf',
                'voltage*current*pf*math.sqrt(3)',
                '1.732*voltage*current*pf',
                'voltage*current*pf*1.732',
            ],
            frozenset(['heat', 'mass', 'specific_heat', 'temperature']): ['mass*specific_heat*temperature'],
            frozenset(['q', 'u', 'a', 'delta_t']): ['u*a*delta_t'],
            frozenset(['thermal_resistance', 'thickness', 'conductivity', 'area']): ['thickness/(conductivity*area)'],
            frozenset(['flow_rate', 'velocity', 'area']): ['velocity*area', 'area*velocity'],
            frozenset(['reynolds', 'density', 'velocity', 'diameter', 'viscosity']): ['density*velocity*diameter/viscosity'],
            frozenset(['pressure_drop', 'flow_rate', 'resistance']): ['flow_rate*resistance'],
            frozenset(['moles', 'mass', 'molecular_weight']): ['mass/molecular_weight'],
            frozenset(['concentration', 'moles', 'volume']): ['moles/volume'],
        }
        self.eng_keywords = {
            'stress', 'force', 'energy', 'power', 'pressure', 'velocity', 'acceleration',
            'mass', 'voltage', 'current', 'resistance', 'temperature', 'density', 'torque',
            'strain', 'moment', 'work', 'heat', 'flow', 'viscosity', 'reynolds', 'conductivity',
            'power_factor', 'pf',
        }

    def _sympy_verify(self, code: str, runtime_output: str) -> tuple[str, str]:
        if not SYMPY_AVAILABLE:
            return ('VERIFICATION_INSUFFICIENT',
                    'Formula not in registry and SymPy not installed — human review required.')
        try:
            tree = ast.parse(code)
            assignments = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            assignments[t.id] = node.value.value
            runtime_nums = [float(x) for x in re.findall(r'\b(\d+(?:\.\d+)?)\b', runtime_output)]
            if runtime_nums and assignments:
                return ('VERIFICATION_INSUFFICIENT',
                        f'Formula not in registry. SymPy context: runtime={runtime_nums[0]}, '
                        f'inputs={assignments}. Human review required.')
        except Exception:
            pass
        return ('VERIFICATION_INSUFFICIENT',
                'Formula not in registry — human review required.')

    def verify(self, code: str, runtime_output: str, draft: str) -> tuple[str, str]:
        if 'Errors:' in runtime_output or 'Exception' in runtime_output:
            return 'FAIL', 'Code execution failed with errors.'

        try:
            tree = ast.parse(code)
        except Exception as e:
            return 'FAIL', f'Syntax error in generated code: {e}'

        computed_exprs = []
        found_eng = False
        has_computation = False

        for node in ast.walk(tree):
            if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.ListComp,
                                  ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                has_computation = True

            if isinstance(node, ast.Assign):
                if isinstance(node.value, (ast.BinOp, ast.UnaryOp, ast.Call)):
                    vars_in_expr = {n.id.lower() for n in ast.walk(node.value)
                                    if isinstance(n, ast.Name)}
                    try:
                        expr_str = ast.unparse(node.value).replace(' ', '').lower()
                        computed_exprs.append((vars_in_expr, expr_str))
                    except Exception:
                        pass
            if isinstance(node, ast.Name) and node.id.lower() in self.eng_keywords:
                found_eng = True

        if not has_computation:
            return ('VERIFICATION_INSUFFICIENT',
                    'No mathematical computations found in code (hardcoded result).')

        verified_formula = False
        for vars_in_expr, expr_str in computed_exprs:
            matched_formula = None
            for req_vars, valid_exprs in self.known_formulas.items():
                if req_vars.issubset(vars_in_expr):
                    matched_formula = valid_exprs
                    break

            if matched_formula:
                if expr_str not in matched_formula:
                    return ('FAIL',
                            f"Incorrect formula detected. Used '{expr_str}', "
                            f"expected one of {matched_formula}.")
                verified_formula = True

        runtime_nums_only = re.findall(r'\b(\d+(?:\.\d+)?)\b', runtime_output)
        draft_nums_only   = re.findall(r'\b(\d+(?:\.\d+)?)\b', draft)

        runtime_matches = re.findall(
            r'\b(\d+(?:\.\d+)?)\s*([a-zA-Z\xb0]+[0-9]*(?:/[a-zA-Z0-9]+)?)\b',
            runtime_output)
        draft_matches = re.findall(
            r'\b(\d+(?:\.\d+)?)\s*([a-zA-Z\xb0]+[0-9]*(?:/[a-zA-Z0-9]+)?)\b',
            draft)

        if not runtime_nums_only and found_eng:
            return ('VERIFICATION_INSUFFICIENT',
                    'No numerical output produced by code execution.')

        for num_str in runtime_nums_only:
            val = float(num_str)
            found = False
            for d_num_str in draft_nums_only:
                d_val = float(d_num_str)
                if d_val == 0:
                    if abs(val) < 1e-6:
                        found = True
                        break
                elif abs(val - d_val) / max(abs(d_val), 1e-9) < 0.01:
                    found = True
                    break

            if not found:
                for r_num_str2, r_unit2 in runtime_matches:
                    if r_num_str2 != num_str:
                        continue
                    for d_num_str2, d_unit2 in draft_matches:
                        if _are_equivalent_units(
                                float(r_num_str2), r_unit2,
                                float(d_num_str2), d_unit2):
                            found = True
                            break
                    if found:
                        break

            if not found:
                return ('FAIL',
                        f'Runtime result {num_str} differs from claimed result in prose '
                        f'(no matching value found, including unit-conversion equivalents).')

        for d_num_str, d_unit in draft_matches:
            d_val = float(d_num_str)
            matched_in_runtime = False
            
            # First check direct numerical matches
            for r_num_str in runtime_nums_only:
                if abs(float(r_num_str) - d_val) / max(abs(d_val), 1e-9) < 0.01:
                    matched_in_runtime = True
                    break
            
            if matched_in_runtime:
                r_units_for_val = [r_unit for r_n, r_unit in runtime_matches if abs(float(r_n) - d_val) / max(abs(d_val), 1e-9) < 0.01]
                
                if not r_units_for_val:
                    return ('FAIL', f"Draft claims '{d_num_str} {d_unit}', but runtime output lacks a unit for this value. The code must explicitly output units (e.g. print('{d_num_str} W')) to verify {d_unit}.")
                else:
                    unit_ok = False
                    for r_unit in r_units_for_val:
                        if r_unit.lower() == d_unit.lower() or _are_equivalent_units(d_val, r_unit, d_val, d_unit):
                            unit_ok = True
                            break
                    if not unit_ok:
                        return ('FAIL', f"Correct numerical result {d_val} with incorrect unit label (claimed '{d_unit}', expected one of {r_units_for_val}).")
            else:
                # Check for unit conversions
                for r_num_str, r_unit in runtime_matches:
                    if _are_equivalent_units(float(r_num_str), r_unit, d_val, d_unit):
                        matched_in_runtime = True
                        break
                if not matched_in_runtime:
                    return ('FAIL', f"Draft claims '{d_num_str} {d_unit}', but this value (or its equivalent) was not produced by the code.")

        if found_eng and not verified_formula and computed_exprs:
            return self._sympy_verify(code, runtime_output)

        return 'PASS', 'Calculation independently verified.'
