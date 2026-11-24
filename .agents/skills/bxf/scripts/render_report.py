#!/usr/bin/env python3
"""Build one offline HTML report from a reviewed brief, calculation result and evidence ledger."""
import argparse
import json
import math
import os
import re
import tempfile
from html import escape
from pathlib import Path
from urllib.parse import urlsplit


SCENARIOS = {"conservative": "保守", "base": "基准", "optimistic": "乐观"}
CELLS = "partners activities resources value relations channels segments costs revenue".split()
TOKENS = re.compile(r"\{\{([\w.]+)\}\}|\[\[([\w.-]+)\]\]")
TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "report.html"


def read(path):
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"需要有限数值，收到 {value!r}")
    return f"{value:,.2f}".rstrip("0").rstrip(".") if not isinstance(value, int) else f"{value:,}"


def display(value):
    if value is None:
        return "未能计算"
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("报告含空白文本")
        return value
    return number(value)


def lookup(obj, path):
    for key in path.split("."):
        if not isinstance(obj, dict) or key not in obj:
            raise ValueError(f"找不到数据字段 {path}")
        obj = obj[key]
    return obj


def chunks(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def table(head, body, css=""):
    headings = "".join(f'<th scope="col">{col}</th>' for col in head)
    rows = []
    for label, *values in body:
        cells = "".join(f"<td>{cell}</td>" for cell in values)
        rows.append(f'<tr><th scope="row">{label}</th>{cells}</tr>')
    return f'<table class="{css}"><thead><tr>{headings}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def render(brief, model, ledger):
    evidence = ledger["records"]
    if len({r["id"] for r in evidence}) != len(evidence):
        raise ValueError("证据编号有重复，请重新运行证据清洗")
    links = {r["id"]: f"#evidence-{i // 3 + 1}" for i, r in enumerate(evidence)}

    def content(raw):
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("简报中的内容必须是非空文本")
        def substitute(match):
            path, ref = match.groups()
            if path:
                return escape(display(lookup(model, path)))
            if ref not in links:
                raise ValueError(f"证据编号 {ref} 不在输入的台账内")
            return f'<a href="{links[ref]}">[{escape(ref)}]</a>'
        parts = []
        end = 0
        for match in TOKENS.finditer(raw):
            parts.extend((escape(raw[end:match.start()]), substitute(match)))
            end = match.end()
        parts.append(escape(raw[end:]))
        result = "".join(parts)
        if "{{" in result or "[[" in result:
            raise ValueError(f"未解析的标记 {raw!r}")
        return result

    def rows(items):
        if not items:
            raise ValueError("内容页需要论据或行动条目")
        return '<div class="rows">' + "".join(
            f'<article class="row"><h3>{content(item["label"])}</h3><p>{content(item["text"])}</p></article>'
            for item in items
        ) + "</div>"

    pages = []
    def add(identifier, title, body):
        if not re.fullmatch(r"[a-z][a-z0-9-]*", identifier) or any(p[0] == identifier for p in pages):
            raise ValueError(f"页锚点应由小写字母数字或连字符组成且唯一：{identifier}")
        pages.append((identifier, content(title), body))

    cover = brief["decision"]
    if cover["verdict"] not in ("推进", "限定范围试点", "补证后决策", "暂缓"):
        raise ValueError("请在约定的四个决策建议中选择一项")
    add("decision", cover["title"], f'<p class="verdict">{content(cover["verdict"])}</p>' + rows(cover["rows"]))
    for page in brief["analysis"]:
        add(page["id"], page["title"], rows(page["rows"]))
    add("canvas", "商业模式画布", "")

    compare = brief["finance"]
    scenarios = [model["scenarios"][key] for key in SCENARIOS]
    metrics = []
    if not compare["metrics"]:
        raise ValueError("财务页至少需要一项带单位的指标")
    for metric in compare["metrics"]:
        metrics.append([content(metric["label"])] + [
            escape(display(lookup(s, metric["path"]))) for s in scenarios
        ])
    chart = compare["chart"]
    values = [lookup(s, chart["path"]) for s in scenarios]
    finite_values = [value for value in values if value is not None]
    for value in finite_values:
        number(value)
        if value < 0:
            raise ValueError("条形图指标须非负，含负数的指标可放在财务表内")
    maximum = max(finite_values, default=0)
    bars = []
    for name, value in zip(SCENARIOS.values(), values):
        width = 100 * value / maximum if value is not None and maximum else 0
        bars.append(f'<div class="barrow"><span>{name}</span><div class="track" aria-hidden="true">'
                    f'<div class="bar" style="width:{width:.4f}%"></div></div><output>{display(value)}</output></div>')
    model_notes = [f"{name}：{escape(note)}" for name, scenario in zip(SCENARIOS.values(), scenarios)
                   for note in scenario.get("notes", [])]
    for i, group in enumerate(chunks(metrics, 7), start=1):
        title = compare["title"] if i == 1 else f'{compare["title"]}（续 {i}）'
        add(f"finance-{i}", title, table(["指标", *SCENARIOS.values()], group, "compare")
            + f'<p class="note">{content(compare["note"])} {" ".join(model_notes)}</p>')
    add("sensitivity", chart["title"], f'<figure class="chart"><figcaption>{content(chart["label"])}</figcaption>'
        + "".join(bars) + "</figure>" + rows(chart["rows"]))
    handoff = brief["handoff"]
    add("handoff", handoff["title"], rows(handoff["rows"]))

    for i, group in enumerate(chunks(evidence, 3), start=1):
        articles = []
        for record in group:
            source = record["source"]
            src = escape(source)
            if urlsplit(source).scheme in {"http", "https"}:
                src = f'<a href="{escape(source, quote=True)}">{src}</a>'
            articles.append(f'<article class="evidence"><h3>{escape(record["id"])} · {escape(record["topic"])}</h3>'
                            f'<p>{escape(record["claim"])}</p><p class="cite">{escape(record["kind"])} · '
                            f'{escape(record["period"])} · {escape(record["unit"])}<br>来源　{src}</p></article>')
        add(f"evidence-{i}", f"附录 · 证据与边界（{i}）", '<div class="records">' + "".join(articles) + "</div>")
    if ledger.get("warnings"):
        for i, group in enumerate(chunks(ledger["warnings"], 4), start=1):
            add(f"conflicts-{i}", f"附录 · 台账核对提示（{i}）", rows([{"label": "待核对", "text": w} for w in group]))
    for i, group in enumerate(chunks(model["assumptions"], 6), start=1):
        params = []
        for item in group:
            ref = item["source"]
            if ref not in links:
                raise ValueError(f"模型参数 {item['label']} 的来源 {ref} 不在本次证据台账内")
            source = content(f"[[{ref}]]")
            params.append([escape(item["label"]), escape(item["unit"])] +
                          [escape(display(item[s])) for s in SCENARIOS] + [source, escape(item["period"])])
        add(f"inputs-{i}", f"附录 · 情景参数（{i}）", table(
            ["变量", "单位", *SCENARIOS.values(), "来源", "期间"], params, "assumptions"))
    for i, group in enumerate(chunks(model["formulas"], 5), start=1):
        add(f"formulas-{i}", f"附录 · 计算口径（{i}）", rows([{"label": f["label"], "text": f["formula"]} for f in group]))
    actions = brief["actions"]
    add("actions", actions["title"], rows(actions["rows"]))

    product = escape(display(model["business"]["product"]))
    version = content(brief["version"])
    status = content(brief["status"])
    canvas = brief["canvas"]
    substitutions = {"TITLE": f"{product} · 可行性决策 · {version}", "CANVAS_NOTE": content(canvas["note"])}
    substitutions.update({key: content(canvas[key]) for key in CELLS})
    sections = []
    for i, (identifier, title, body) in enumerate(pages, start=1):
        meta = f'<header class="meta"><span>{product}</span><span>{version}</span></header>'
        foot = f'<footer class="footer"><span>{status}</span><span>第 {i} / {len(pages)} 页</span></footer>'
        if identifier == "canvas":
            substitutions.update(CANVAS_HEAD=meta, CANVAS_FOOT=foot, BEFORE="\n".join(sections))
            sections = []
            continue
        tag = "h1" if i == 1 else "h2"
        css = "slide cover" if i == 1 else "slide"
        sections.append(f'<section class="{css}" id="{identifier}" tabindex="-1" aria-labelledby="title-{identifier}">'
                        f'{meta}<{tag} id="title-{identifier}">{title}</{tag}>{body}{foot}</section>')
    substitutions["AFTER"] = "\n".join(sections)
    return re.sub(r"@@(\w+)@@", lambda match: substitutions[match[1]], TEMPLATE.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("brief", "model", "evidence", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.output.resolve() in {p.resolve() for p in (args.brief, args.model, args.evidence, TEMPLATE)}:
            raise ValueError("请使用独立的报告输出路径，以保留简报、模型、证据和模板")
        result = render(read(args.brief), read(args.model), read(args.evidence))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent, delete=False) as tmp:
            tmp.write(result)
        os.replace(tmp.name, args.output)
    except (KeyError, ValueError, TypeError, OSError) as error:
        parser.exit(2, f"生成报告失败：{error}\n")
    print(args.output)


if __name__ == "__main__":
    main()
