"""
Tier 1 Dolton: Overtime Anomaly Detection

Detection Focus: Impossible or suspicious overtime patterns.

Key finding from Dolton:
- Police officer logged 332 hours in a 336-hour pay period
- That's 98.8% of all hours in a 14-day period
"""

from typing import Optional
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, dual_hash, TENANT_ID, stoprule_alert


# Time constants
HOURS_PER_DAY = 24
HOURS_PER_WEEK = 168
HOURS_PER_BIWEEKLY = 336
STANDARD_WORK_WEEK = 40
MAX_REASONABLE_HOURS_WEEK = 80  # Even this is extreme


def compute_overtime_ratio(payroll: list[dict], employee: str) -> dict:
    """
    Compute overtime to regular hours ratio for an employee.

    Args:
        payroll: Payroll records with employee, regular_hours, overtime_hours
        employee: Employee ID to analyze

    Returns:
        Dict with OT ratio metrics
    """
    employee_records = [p for p in payroll if p.get("employee") == employee]

    if not employee_records:
        return {
            "employee": employee,
            "total_regular": 0,
            "total_overtime": 0,
            "ot_ratio": 0,
            "records": 0
        }

    total_regular = sum(p.get("regular_hours", 0) for p in employee_records)
    total_overtime = sum(p.get("overtime_hours", 0) for p in employee_records)
    total_hours = total_regular + total_overtime

    return {
        "employee": employee,
        "total_regular": total_regular,
        "total_overtime": total_overtime,
        "total_hours": total_hours,
        "ot_ratio": total_overtime / total_regular if total_regular > 0 else float('inf'),
        "ot_percentage": total_overtime / total_hours if total_hours > 0 else 0,
        "records": len(employee_records)
    }


def detect_impossible_hours(payroll: list[dict],
                             period_hours: int = None) -> list[dict]:
    """
    Flag employees with hours exceeding period maximum.

    Args:
        payroll: Payroll records with employee, total_hours, period_start, period_end
        period_hours: Hours in pay period (default: 336 for biweekly)

    Returns:
        List of impossible hours flags
    """
    if period_hours is None:
        period_hours = HOURS_PER_BIWEEKLY

    # Group by employee and period
    employee_periods = {}
    for record in payroll:
        emp = record.get("employee", "unknown")
        period = record.get("period", "default")
        key = f"{emp}:{period}"

        if key not in employee_periods:
            employee_periods[key] = {
                "employee": emp,
                "period": period,
                "total_hours": 0,
                "records": []
            }

        hours = record.get("total_hours", 0)
        if hours == 0:
            hours = record.get("regular_hours", 0) + record.get("overtime_hours", 0)

        employee_periods[key]["total_hours"] += hours
        employee_periods[key]["records"].append(record)

    flags = []
    for key, data in employee_periods.items():
        if data["total_hours"] > period_hours:
            flags.append({
                "flag_type": "impossible_hours",
                "employee": data["employee"],
                "period": data["period"],
                "reported_hours": data["total_hours"],
                "period_hours": period_hours,
                "excess_hours": data["total_hours"] - period_hours,
                "impossibility_ratio": data["total_hours"] / period_hours,
                "severity": "critical"
            })
        elif data["total_hours"] > period_hours * 0.8:
            # Flag extremely high but not impossible
            flags.append({
                "flag_type": "extreme_hours",
                "employee": data["employee"],
                "period": data["period"],
                "reported_hours": data["total_hours"],
                "period_hours": period_hours,
                "utilization_ratio": data["total_hours"] / period_hours,
                "severity": "high"
            })

    return flags


def detect_overtime_patterns(payroll: list[dict]) -> list[dict]:
    """
    Detect suspicious overtime patterns across employees.

    Args:
        payroll: Payroll records

    Returns:
        List of pattern flags
    """
    # Get all employees
    employees = set(p.get("employee") for p in payroll if p.get("employee"))

    patterns = []
    high_ot_employees = []

    for emp in employees:
        metrics = compute_overtime_ratio(payroll, emp)

        # Flag high OT ratios
        if metrics["ot_ratio"] > 1.0:  # More OT than regular
            high_ot_employees.append({
                "employee": emp,
                "ot_ratio": metrics["ot_ratio"],
                "total_overtime": metrics["total_overtime"]
            })

        # Flag employees with OT every period
        emp_records = [p for p in payroll if p.get("employee") == emp]
        ot_records = [p for p in emp_records if p.get("overtime_hours", 0) > 0]

        if len(ot_records) == len(emp_records) and len(emp_records) > 2:
            patterns.append({
                "flag_type": "consistent_overtime",
                "employee": emp,
                "periods_with_ot": len(ot_records),
                "total_periods": len(emp_records),
                "severity": "medium"
            })

    # Check for department-wide OT patterns
    if len(high_ot_employees) > 3:
        patterns.append({
            "flag_type": "systemic_overtime",
            "high_ot_count": len(high_ot_employees),
            "employees": [e["employee"] for e in high_ot_employees[:10]],
            "severity": "high"
        })

    return patterns


def compute_overtime_cost(payroll: list[dict],
                           regular_rate_field: str = "hourly_rate",
                           ot_multiplier: float = 1.5) -> dict:
    """
    Compute total overtime cost and compare to regular pay.

    Args:
        payroll: Payroll records
        regular_rate_field: Field name for hourly rate
        ot_multiplier: OT pay multiplier (default 1.5x)

    Returns:
        Dict with cost analysis
    """
    total_regular_pay = 0
    total_ot_pay = 0

    for record in payroll:
        rate = record.get(regular_rate_field, 0)
        regular_hours = record.get("regular_hours", 0)
        ot_hours = record.get("overtime_hours", 0)

        total_regular_pay += rate * regular_hours
        total_ot_pay += rate * ot_multiplier * ot_hours

    total_pay = total_regular_pay + total_ot_pay

    return {
        "regular_pay": total_regular_pay,
        "overtime_pay": total_ot_pay,
        "total_pay": total_pay,
        "ot_cost_ratio": total_ot_pay / total_pay if total_pay > 0 else 0,
        "ot_premium_cost": total_ot_pay - (total_ot_pay / ot_multiplier)  # Extra cost of OT vs regular
    }


def overtime_receipt(payroll: list[dict], entity: str = "dolton") -> dict:
    """
    Emit receipt with overtime analysis results.

    Args:
        payroll: Payroll records
        entity: Entity name

    Returns:
        Receipt dict
    """
    impossible = detect_impossible_hours(payroll)
    patterns = detect_overtime_patterns(payroll)
    costs = compute_overtime_cost(payroll)

    # Compute severity
    if any(f.get("flag_type") == "impossible_hours" for f in impossible):
        severity = "critical"
    elif any(f.get("severity") == "high" for f in impossible + patterns):
        severity = "high"
    elif impossible or patterns:
        severity = "medium"
    else:
        severity = "low"

    receipt = emit_receipt("tier1", {
        "tenant_id": TENANT_ID,
        "finding_type": "overtime_analysis",
        "entity": entity,
        "severity": severity,
        "evidence_hash": dual_hash(str(payroll[:100]).encode()),
        "dollar_value": costs["overtime_pay"],
        "overtime_flags": {
            "impossible_hours": len([f for f in impossible if f.get("flag_type") == "impossible_hours"]),
            "extreme_hours": len([f for f in impossible if f.get("flag_type") == "extreme_hours"]),
            "consistent_overtime": len([f for f in patterns if f.get("flag_type") == "consistent_overtime"]),
            "systemic_overtime": len([f for f in patterns if f.get("flag_type") == "systemic_overtime"])
        },
        "cost_analysis": {
            "regular_pay": costs["regular_pay"],
            "overtime_pay": costs["overtime_pay"],
            "ot_cost_ratio": costs["ot_cost_ratio"]
        },
        "flags": impossible + patterns
    })

    # Alert on impossible hours
    for flag in impossible:
        if flag.get("flag_type") == "impossible_hours":
            stoprule_alert(
                metric="impossible_hours",
                message=f"Impossible hours for {flag['employee']}: {flag['reported_hours']}/{flag['period_hours']}",
                baseline=flag["period_hours"],
                delta=flag["excess_hours"]
            )

    return receipt
