#!/usr/bin/env python3
"""Recompute one explicit period/unit scenario. Stdlib only; never sets prices."""
import argparse
import json
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from pathlib import Path


def number(value, label):
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{label}: explicit non-negative number required; unknown is not zero")
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"{label}: invalid number") from exc
    if not n.is_finite() or n < 0:
        raise ValueError(f"{label}: finite non-negative number required")
    return n


def calculate(data):
    for key in ('period_label', 'unit_label'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f'{key}: name the period and quantity unit')
    budget, existing, buffer, shared = [number(data.get(k), k) for k in
        ('period_hours', 'existing_hours', 'buffer_hours', 'shared_hours')]
    parts = data.get('per_unit_hours')
    if not isinstance(parts, dict) or not parts:
        raise ValueError('per_unit_hours: explicit component hours required')
    unit_hours = sum((number(v, k) for k, v in parts.items()), Decimal(0))
    if unit_hours == 0:
        raise ValueError('per-unit hours must be positive; zero does not prove unlimited capacity')
    remainder = budget - existing - buffer - shared
    capacity = int((max(Decimal(0), remainder) / unit_hours).to_integral_value(rounding=ROUND_FLOOR))
    cap = data.get('quality_cap_units')
    if cap is not None:
        cap = number(cap, 'quality_cap_units')
        if cap != cap.to_integral_value():
            raise ValueError('quality_cap_units: whole units required')
        capacity = min(capacity, int(cap))
    units = number(data.get('scenario_units'), 'scenario_units')
    if units != units.to_integral_value():
        raise ValueError('scenario_units: whole units required')
    result = {'period_label': data['period_label'], 'unit_label': data['unit_label'],
        'remaining_hours_after_shared': float(remainder), 'hours_per_unit': float(unit_hours),
        'capacity_units': capacity, 'scenario_units': int(units),
        'scenario_feasible_by_total_hours': bool(remainder >= 0 and units <= capacity),
        'scenario_new_hours': float(shared + units * unit_hours),
        'calendar_peak_verified': False,
        'limitations': ['Same-period arithmetic only; calendar peaks, multiple periods and demand need separate evidence.']}
    money_keys = ('price_per_unit', 'cash_cost_per_unit', 'fixed_cash_cost', 'fee_rate')
    supplied = [k in data for k in money_keys]
    if any(supplied) and not all(supplied):
        raise ValueError('For a cash scenario provide all four money inputs; unknown is not zero')
    if all(supplied):
        price, cost, fixed, fee = [number(data[k], k) for k in money_keys]
        if fee > 1:
            raise ValueError('fee_rate: use a fraction between 0 and 1')
        revenue = price * units
        fees = revenue * fee
        direct = cost * units
        cash = revenue - fees - direct - fixed
        owner = data.get('owner_hourly_value')
        imputed = None if owner is None else number(owner, 'owner_hourly_value') * (shared + units * unit_hours)
        result['cash_scenario'] = {'gross_revenue': float(revenue), 'channel_fees': float(fees),
            'variable_cash_cost': float(direct), 'fixed_cash_cost': float(fixed),
            'cash_surplus_before_owner_time_and_unlisted_costs': float(cash),
            'owner_time_imputed_cost': None if imputed is None else float(imputed),
            'surplus_after_imputed_owner_time_before_unlisted_costs': None if imputed is None else float(cash - imputed),
            'is_net_profit': False}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='UTF-8 JSON scenario; see skill input example')
    args = parser.parse_args()
    try:
        print(json.dumps(calculate(json.loads(args.input.read_text(encoding='utf-8-sig'))), ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
