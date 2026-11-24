#!/usr/bin/env python3
"""Model monthly recurring revenue, service capacity, and cash settlement."""

import argparse
import json
import re
from collections import defaultdict
from decimal import Decimal, DecimalException, ROUND_CEILING
from pathlib import Path

from research import write_json


SCENARIOS = ("base", "optimistic", "conservative")
# Each field has one canonical unit. The currency is taken from the business context.
FIELDS = {
    "leads": ("每月独立触达的潜在客户", "客户/月"),
    "conversion": ("触达后成为付费客户的比例", "比例"),
    "onboarding_capacity": ("每月接入能力", "客户/月"),
    "active_capacity": ("可同时服务的客户上限", "客户"),
    "retention": ("上月活跃客户本月留存率", "比例"),
    "price": ("含退款前的月订阅报价", "{currency}/客户/月"),
    "refund": ("按当月账单金额计的退款率", "比例"),
    "share": ("按退款后收入计的平台分成率", "比例"),
    "variable_cost": ("每活跃客户月履约支出", "{currency}/客户/月"),
    "cac": ("每新增客户获客支出", "{currency}/新客户"),
    "fixed": ("每月固定运营支出", "{currency}/月"),
    "setup": ("期初一次性启动支出", "{currency}"),
    "collection_lag": ("客户回款账期", "月"),
    "payment_lag": ("履约费付款账期", "月"),
}
FORMULAS = [
    ("容量与留存", "留存 = 上月活跃 × 留存率；漏斗新签 = min(触达 × 转化率，月接入上限)；实际新签 = min(漏斗新签，并行上限 − 留存)。"),
    ("可得客户", "当月活跃 = 留存 + 实际新签。当期累计新签为各月实际新签之和。初始客户为零，小数客户为规划期望值。"),
    ("收入与贡献", "净收入 = 活跃 × 月报价 × (1 − 退款率)；贡献 = 净收入 × (1 − 分成率) − 活跃 × 单位履约费。"),
    ("期间经营结果", "各月贡献减去各月固定费和实际新签 × 获客成本后加总。一次性启动支出单列入现金流。"),
    ("单月保本", "期末月所需活跃数 = (固定费 + 期末月获客支出) ÷ 单位贡献，向上取整；计算假定该月获客支出不变。"),
    ("期末临界月价", "在期末月活跃量与新签量不变时，((固定费 + 该月获客支出) ÷ 活跃量 + 单位履约费) ÷ [(1 − 退款率) × (1 − 分成率)]，向上取分。"),
    ("资金峰值", "月末累计现金从负启动支出起算；净收入扣分成后按回款账期收现；履约费按付款账期支付，固定费与获客费当月付。最低累计现金取负即峰值资金需求，含尾款结清。"),
]


def require_text(mapping, field):
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} 缺少非空文本")
    return value.strip()


def check_keys(actual, expected, context):
    if not isinstance(actual, dict):
        raise ValueError(f"{context} 应为 JSON 对象")
    missing = set(expected) - actual.keys()
    extra = actual.keys() - set(expected)
    if missing or extra:
        raise ValueError(f"{context} 缺少 {sorted(missing)}，多出 {sorted(extra)}")


def inputs_from(data, evidence):
    check_keys(data, ("business", "parameters"), "模型")
    business = data["business"]
    business_keys = ("product", "customer", "user", "payer", "channel", "billing", "currency",
                     "region", "period", "months")
    check_keys(business, business_keys, "business")
    for field in business_keys[:-1]:
        require_text(business, field)
    if not re.fullmatch(r"[A-Z]{3}", business["currency"]):
        raise ValueError("currency 应为三位大写货币代码，如 CNY")
    if type(business["months"]) is not int or business["months"] <= 0:
        raise ValueError("months 必须为正整数月数")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("records"), list):
        raise ValueError("请提供 research.py 生成的证据台账 JSON")
    source_ids = {row["id"] for row in evidence["records"] if isinstance(row, dict) and "id" in row}
    parameters = data["parameters"]
    check_keys(parameters, FIELDS, "parameters")
    assumptions = []
    scenarios = {name: {} for name in SCENARIOS}
    for key, (label, unit_pattern) in FIELDS.items():
        item = parameters[key]
        check_keys(item, ("unit", "source", "period", *SCENARIOS), key)
        unit = unit_pattern.format(currency=business["currency"])
        if item["unit"] != unit:
            raise ValueError(f"{key} 单位应为 {unit}，收到 {item['unit']}，请按来源换算后输入")
        source = require_text(item, "source")
        if source not in source_ids:
            raise ValueError(f"{key} 的证据编号 {source} 在台账中不存在")
        require_text(item, "period")
        for name in SCENARIOS:
            value = item[name]
            if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
                raise ValueError(f"{key}.{name} 缺少 JSON 数值，须显式提供（比例用 0 至 1）")
            number = Decimal(value)
            if not number.is_finite() or number < 0:
                raise ValueError(f"{key}.{name} 须提供有限的非负数")
            if unit == "比例" and number > 1:
                raise ValueError(f"{key}.{name} 超过 1，请将百分数换算成比例")
            if key in ("collection_lag", "payment_lag") and number != number.to_integral_value():
                raise ValueError(f"{key}.{name} 应为整月账期")
            scenarios[name][key] = number
        assumptions.append({"key": key, "label": label, **item})
    return business, assumptions, scenarios


def calculate(p, months):
    retained_fraction = (1 - p["refund"]) * (1 - p["share"])
    unit_contribution = p["price"] * retained_fraction - p["variable_cost"]
    funnel = min(p["leads"] * p["conversion"], p["onboarding_capacity"])
    active = Decimal(0)
    months_detail = []
    inflows = defaultdict(Decimal)
    outflows = defaultdict(Decimal)
    for month in range(1, months + 1):
        kept = active * p["retention"]
        new = min(funnel, p["active_capacity"] - kept)
        active = kept + new
        revenue = active * p["price"] * (1 - p["refund"])
        service = active * p["variable_cost"]
        contribution = revenue * (1 - p["share"]) - service
        acquisition = new * p["cac"]
        operating = contribution - acquisition - p["fixed"]
        months_detail.append(dict(month=month, new=new, active=active, revenue=revenue,
                                  contribution=contribution, acquisition=acquisition,
                                  operating_result=operating))
        inflows[month + int(p["collection_lag"])] += revenue * (1 - p["share"])
        outflows[month + int(p["payment_lag"])] += service
        outflows[month] += acquisition + p["fixed"]

    cash = lowest = -p["setup"]
    cash_schedule = [{"month": 0, "inflow": 0, "outflow": p["setup"], "balance": cash}]
    for month in sorted(inflows.keys() | outflows.keys()):
        received, paid = inflows[month], outflows[month]
        cash += received - paid
        lowest = min(lowest, cash)
        cash_schedule.append(dict(month=month, inflow=received, outflow=paid, balance=cash))

    last = months_detail[-1]
    monthly_overhead = last["acquisition"] + p["fixed"]
    notes = []
    required_active = required_price = None
    if unit_contribution > 0:
        required_active = (monthly_overhead / unit_contribution).to_integral_value(rounding=ROUND_CEILING)
        if required_active > p["active_capacity"]:
            notes.append("期末月保本所需活跃客户数超过服务上限。")
    elif unit_contribution == 0 and monthly_overhead == 0:
        required_active = 0
    else:
        notes.append("单位贡献非正，在期末月获客与固定支出下无法靠增加客户达到单月保本。")
    if active > 0 and retained_fraction > 0:
        price = (monthly_overhead / active + p["variable_cost"]) / retained_fraction
        required_price = price.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    else:
        notes.append("期末无活跃客户或退款分成后无收入可得，无法推导有效的临界月价。")

    summary = {
        "new_per_month": funnel,
        "new_total": sum(row["new"] for row in months_detail),
        "net_revenue": sum(row["revenue"] for row in months_detail),
        "contribution": sum(row["contribution"] for row in months_detail),
        "operating_result": sum(row["operating_result"] for row in months_detail),
        "peak_cash_need": -lowest,
        "ending_active": active,
        "break_even_active": required_active,
        "break_even_price": required_price,
        "unit_contribution": unit_contribution,
    }
    return dict(inputs=p, summary=summary, monthly=months_detail, cash_schedule=cash_schedule, notes=notes)


def json_ready(value):
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def main():
    parser = argparse.ArgumentParser(description="按月订阅模型，输出三情景、现金时序与保本阈值")
    for filename in ("input", "evidence", "output"):
        parser.add_argument(filename, type=Path)
    args = parser.parse_args()
    try:
        if args.output.resolve() in (args.input.resolve(), args.evidence.resolve()):
            raise ValueError("输入和输出须使用不同路径")
        data = json.loads(args.input.read_text(encoding="utf-8-sig"), parse_float=Decimal)
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        business, assumptions, scenarios = inputs_from(data, evidence)
        result = {"business": business, "assumptions": assumptions,
                  "formulas": [{"label": label, "formula": formula} for label, formula in FORMULAS],
                  "scenarios": {key: calculate(values, business["months"]) for key, values in scenarios.items()}}
        write_json(args.output, json_ready(result))
    except (OSError, ValueError, DecimalException, OverflowError) as error:
        parser.exit(2, f"财务测算错误：{error}\n")
    print(f"已写入 {len(scenarios)} 个情景：{args.output}")
    for key, scenario in result["scenarios"].items():
        for note in scenario["notes"]:
            print(f"{key}：{note}")


if __name__ == "__main__":
    main()
