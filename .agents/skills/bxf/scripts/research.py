#!/usr/bin/env python3
"""Normalize a UTF-8 evidence ledger; retain conflicts for human review."""

import argparse
import csv
import json
import tempfile
from collections import defaultdict
from pathlib import Path


FIELDS = ("id", "kind", "topic", "claim", "source", "period", "unit")
KINDS = {"可核查事实", "外部估算", "用户输入", "模型推断", "待验证假设"}


def write_json(path, data):
    """Publish a complete JSON document, keeping an existing output on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(payload)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def normalize(path):
    records = {}
    by_topic = defaultdict(list)
    repeated = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        if len(set(columns)) != len(columns) or set(columns) != set(FIELDS):
            raise ValueError(f"表头必须逐列提供 {', '.join(FIELDS)}，请检查缺失、重复或多余的列")
        for raw in reader:
            if None in raw:
                raise ValueError(f"第 {reader.line_num} 行字段过多，请用双引号包住含英文逗号的文本")
            row = {key: (raw[key] or "").strip() for key in FIELDS}
            for key, value in row.items():
                if not value:
                    raise ValueError(f"第 {reader.line_num} 行缺少 {key}")
            if row["kind"] not in KINDS:
                raise ValueError(f"第 {reader.line_num} 行 kind 类型无效，可选 {', '.join(sorted(KINDS))}")
            code = row["id"]
            if code in records:
                if records[code] != row:
                    raise ValueError(f"{code} 对应不同内容，请核对原始记录或分配独立证据编号")
                repeated += 1
                continue
            records[code] = row
            by_topic[(row["topic"], row["period"])].append(row)
    if not records:
        raise ValueError("证据台账为空。如无可核查事实，可记录待验证假设及提出它的依据")
    warnings = []
    for (topic, period), group in by_topic.items():
        if len({row["unit"] for row in group}) > 1:
            ids = "、".join(row["id"] for row in group)
            warnings.append(f"{topic}（{period}，{ids}）的单位不同；取得换算依据前保留分列")
        elif len({row["claim"] for row in group}) > 1:
            ids = "、".join(row["id"] for row in group)
            warnings.append(f"{topic}（{period}，{ids}）有多个表述；合并前核对定义、样本与来源")
    return {"records": list(records.values()), "duplicates_removed": repeated, "warnings": warnings}


def main():
    parser = argparse.ArgumentParser(description="清洗 UTF-8 CSV 证据台账，输出可追溯 JSON")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("输入和输出须使用不同路径")
        result = normalize(args.input)
        write_json(args.output, result)
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(2, f"调研台账错误：{error}\n")
    print(f"{len(result['records'])} 条证据，删除 {result['duplicates_removed']} 条重复行，写入 {args.output}")
    for warning in result["warnings"]:
        print(warning)


if __name__ == "__main__":
    main()
