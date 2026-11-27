#!/usr/bin/env python3
"""Compile a reviewed feasibility brief to a themed, standalone slide presentation."""
import argparse
import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from report_layout import (CELLS, IDENTIFIER, SCENARIOS, Content, Part, display, join, pack,
                           page_parts, plain, table_parts, width)


ASSETS = Path(__file__).resolve().parents[1] / "assets"
TEMPLATE = ASSETS / "report.html"
VERDICTS = {"推进", "限定范围试点", "补证后决策", "暂缓"}


def read(path):
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def write_html(path, contents):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
            name = file.name
            file.write(contents)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


class Literal(Content):
    """The ledger is source material, not a template."""
    def __call__(self, text):
        return escape(display(text))


def evidence_pages(ledger):
    parts, records, links = [], ledger["records"], {}
    literal = Literal({}, {})
    ids = [r["id"] for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError("证据编号重复，请重新清洗台账")
    # Each record stays attached to its source, unit and period, including on continuations.
    origins = {}
    for record in records:
        ref = record["id"]
        heading = f'{escape(ref)} · {escape(record["topic"])}'
        source = escape(record["source"])
        if urlsplit(record["source"]).scheme in {"http", "https"}:
            source = f'<a href="{source}">{source}</a>'
        context = " · ".join(escape(record[k]) for k in ("kind", "period", "unit"))
        for i, chunk in enumerate(literal.split(record["claim"], 170)):
            label = heading + ("（续）" if i else "")
            html = (f'<article class="evidence"><h3>{label}</h3><p>{escape(chunk)}</p>'
                    f'<p class="cite">{context}<br>来源　{source}</p></article>')
            weight = max(4, 2 + math.ceil(width(chunk + record["source"]) / 54))
            part = Part(html, weight, '<div class="records">', '</div>')
            parts.append(part)
            origins[part] = ref
    pages = pack(parts)
    for i, group in enumerate(pages, 1):
        for part in group:
            links.setdefault(origins[part], f"evidence-{i}")
    return pages, links


@dataclass
class Page:
    id: str
    title: str
    chapter: str
    label: str
    kind: str
    body: str
    heading_extra: str = ""


class Compiler:
    def __init__(self, brief, model, ledger, preview):
        self.brief, self.model, self.ledger = brief, model, ledger
        self.evidence, links = evidence_pages(ledger)
        self.content = Content(model, links, preview)
        self.pages, self.anchors = [], set()

    def add(self, page):
        if not IDENTIFIER.fullmatch(page.id) or page.id in self.anchors:
            raise ValueError(f"页锚点须唯一且仅含小写字母、数字或连字符：{page.id}")
        self.anchors.add(page.id)
        self.pages.append(page)

    def section(self, spec, chapter, label, kind, key=None, extra="", capacity=12,
                sequence_ids=False, extra_note=""):
        content = self.content
        key = key or spec["id"]
        title = content(spec["title"])
        parts = page_parts(spec, self.model, content)
        # A short qualification accompanies every split table. Long qualifications are
        # preserved in full immediately afterwards with the same title and citation links.
        notes = [content(s) for s in content.split(spec["note"], 150)] if spec.get("note") else []
        if extra_note:
            notes.append(extra_note)
        if len(notes) > 1 and width(plain(" ".join(notes))) <= 180:
            notes = [" ".join(notes)]
        note = notes[0] if notes else ""
        if note:
            capacity = max(3, capacity - max(1, math.ceil(width(plain(note)) / 90)))
            note = f'<p class="note">{note}</p>'
        pages = [(join(group) + note) for group in pack(parts, capacity)]
        if len(notes) > 1:
            rest = [Part(f'<p class="note">{n}</p>', max(2, math.ceil(width(plain(n)) / 60))) for n in notes[1:]]
            pages.extend(join(group) for group in pack(rest, 10))
        for i, body in enumerate(pages, 1):
            identifier = f"{key}-{i}" if sequence_ids else (key if i == 1 else f"{key}-p{i}")
            heading = title if i == 1 else f'{title}（续 {i}）'
            self.add(Page(identifier, heading, chapter, label, kind if i == 1 or kind != 'cover' else 'analysis',
                          body, extra if i == 1 else ""))

    def cover(self):
        cover = self.brief["decision"]
        verdict = cover["verdict"]
        if verdict not in VERDICTS:
            raise ValueError("请在约定的四个决策建议中选择一项")
        extra = f'<p class="verdict">{self.content(verdict)}</p>'
        metrics = cover.get("metrics", [])
        if not isinstance(metrics, list) or len(metrics) > 2:
            raise ValueError("封面可选填零至两项关键指标")
        if metrics:
            items = []
            for item in metrics:
                value = item["value"]
                rendered = self.content(value) if isinstance(value, str) else escape(display(value))
                unit = self.content(item["unit"]) if item.get("unit") else ""
                items.append(f'<article class="metric"><span class="metric-label">{self.content(item["label"])}</span>'
                             f'<strong class="metric-value">{rendered}</strong><span class="metric-unit">{unit}</span></article>')
            extra += '<div class="cover-metrics">' + "".join(items) + '</div>'
        # Cover metrics occupy the heading column, not the flow of the decision arguments.
        self.section({k: v for k, v in cover.items() if k != "metrics"},
                     "decision", "决策摘要", "cover", key="decision", extra=extra, capacity=9)

    def canvas(self):
        data = self.brief["canvas"]
        cells = []
        for key, label in CELLS.items():
            text = self.content(data[key])
            if width(plain(text)) > 110:
                raise ValueError(f"画布「{label}」超过单格容量，请保留一句结论和证据编号，并将展开论证编入正文")
            cells.append(f'<article class="cell {key}" data-cell="{key}" style="grid-area:{key}"><h3>'
                         f'<button class="cell-trigger" type="button" aria-pressed="false">{label}</button>'
                         f'</h3><p>{text}</p></article>')
        note = f'<p class="note">{self.content(data["note"])}</p>' if data.get("note") else ""
        self.add(Page("canvas", "商业模式画布", "canvas", "商业模式", "canvas-slide",
                      '<div class="canvas">' + "".join(cells) + '</div>' + note))

    def chapters(self):
        brief = self.brief
        if "chapters" in brief and "analysis" in brief:
            raise ValueError("chapters 与旧版 analysis 请选择一种，以免丢失分析内容")
        chapter_ids = set()
        for chapter in brief.get("chapters", []):
            key = chapter["id"]
            if not IDENTIFIER.fullmatch(key) or key in chapter_ids:
                raise ValueError(f"章节编号无效或重复：{key}")
            chapter_ids.add(key)
            if key == "canvas":
                if set(chapter) != {"id"}:
                    raise ValueError("画布占位仅接受 {id: canvas}，内容放在 brief.canvas")
                self.canvas()
            else:
                label = self.content(chapter["label"])
                if not chapter["pages"]:
                    raise ValueError(f"章节 {key} 没有内容")
                for spec in chapter["pages"]:
                    self.section(spec, key, label, "analysis")
        for spec in brief.get("analysis", []):
            self.section(spec, spec["id"], "业务分析", "analysis")
        if "canvas" not in self.anchors:
            self.canvas()

    def finance(self):
        finance = self.brief.get("finance")
        if finance is None:
            return
        notes = []
        for key, label in SCENARIOS.items():
            scenario = self.model.get("scenarios", {}).get(key, {})
            notes.extend(f"{label}：{escape(n)}" for n in scenario.get("notes", []))
        model_note = " ".join(notes)
        if "pages" in finance:
            if any(k in finance for k in ("metrics", "chart", "note")):
                raise ValueError("finance.pages 和旧版 finance.metrics/chart/note 不能混用，请将内容放进具体页")
            entries = finance["pages"]
            if not entries:
                raise ValueError("财务章节缺少内容页")
            for i, spec in enumerate(entries):
                self.section(spec, "finance", "财务分析", "finance",
                             extra_note=model_note if i == 0 else "")
            return
        main = {k: v for k, v in finance.items() if k != "chart"}
        self.section(main, "finance", "财务分析", "finance", key="finance",
                     sequence_ids=True, capacity=10, extra_note=model_note)
        if "chart" in finance:
            chart = finance["chart"]
            self.section({"title": chart["title"], "chart": chart, "rows": chart.get("rows", [])},
                         "finance", "财务分析", "finance", key="sensitivity")

    def appendix(self):
        for i, parts in enumerate(self.evidence, 1):
            self.add(Page(f"evidence-{i}", f"附录 · 证据与边界（{i}）", "evidence", "证据附录", "appendix", join(parts)))
        warnings = self.ledger.get("warnings", [])
        if warnings:
            self.section({"title": "附录 · 台账核对提示", "rows": [{"label": "待核对", "text": w} for w in warnings]},
                         "evidence", "证据附录", "appendix", key="conflicts", sequence_ids=True)
        if self.brief.get("finance") is None:
            # Scenario warnings also belong in a custom chapter-based report.
            notes = [{"label": label, "text": note} for key, label in SCENARIOS.items()
                     for note in self.model.get("scenarios", {}).get(key, {}).get("notes", [])]
            if notes:
                self.section({"title": "附录 · 情景测算提示", "rows": notes},
                             "inputs", "模型附录", "appendix", key="model-notes", sequence_ids=True)
        params = []
        for item in self.model.get("assumptions", []):
            params.append([escape(item["label"]), escape(item["unit"]),
                           *(escape(display(item[s])) for s in SCENARIOS),
                           self.content("[[" + item["source"] + "]]"), escape(item["period"])])
        if params:
            parts = table_parts(["变量", "单位", *SCENARIOS.values(), "来源", "期间"], params, "assumptions")
            for i, batch in enumerate(pack(parts, 10), 1):
                self.add(Page(f"inputs-{i}", f"附录 · 情景参数（{i}）", "inputs", "模型附录", "appendix", join(batch)))
        formulas = self.model.get("formulas", [])
        if formulas:
            self.section({"title": "附录 · 计算口径", "rows": [{"label": f["label"], "text": f["formula"]} for f in formulas]},
                         "formulas", "模型附录", "appendix", key="formulas", sequence_ids=True)

    def compile(self, preview):
        self.cover()
        if preview:
            # The visual sample contains the actual opening slide and the whole canvas.
            self.pages, self.anchors = self.pages[:1], {"decision"}
            self.canvas()
            return self.pages
        self.chapters()
        self.finance()
        if "handoff" in self.brief:
            self.section(self.brief["handoff"], "handoff", "范围与约束", "analysis", key="handoff")
        self.appendix()
        if "actions" in self.brief:
            self.section(self.brief["actions"], "actions", "验证计划", "analysis", key="actions")
        return self.pages


def render(brief, model, ledger, theme="boardroom", preview=False):
    themes = read(ASSETS / "themes.json")
    if theme not in themes:
        raise ValueError(f"未知主题 {theme}；可选 {', '.join(themes)}")
    compiler = Compiler(brief, model, ledger, preview)
    version = escape(plain(compiler.content(brief["version"])))
    status = compiler.content(brief["status"])
    product = escape(display(model["business"]["product"]))
    pages = compiler.compile(preview)
    slides = []
    for i, page in enumerate(pages, 1):
        tag = "h1" if i == 1 else "h2"
        page_no = f"{i:02d} / {len(pages):02d}"
        slides.append(f'<section class="slide {page.kind}" data-kind="{page.kind}" data-chapter="{page.chapter}" '
                      f'id="{page.id}" tabindex="-1" aria-labelledby="title-{page.id}">'
                      f'<header class="meta"><span class="product">{product}</span><span class="section-label">{page.label}</span>'
                      f'<span class="version">{version}</span></header><div class="page-frame"><div class="page-heading">'
                      f'<{tag} id="title-{page.id}">{page.title}</{tag}>{page.heading_extra}</div>'
                      f'<div class="page-body">{page.body}</div></div><footer class="footer"><span class="status">{status}</span>'
                      f'<span class="folio" aria-label="第 {i} 页，共 {len(pages)} 页">{page_no}</span></footer></section>')
    reveal = (ASSETS / "vendor/reveal.js").read_text(encoding="utf-8")
    reveal = re.sub(r"(?m)^[ \t]*//[#@]\s*sourceMappingURL=.*$", "", reveal)
    # In an HTML script block, even a comment must not contain a literal closing script tag.
    reveal = re.sub(r"</script", r"<\\/script", reveal, flags=re.I)
    license_text = (ASSETS / "vendor/reveal.LICENSE").read_text(encoding="utf-8").replace("*/", "* /")
    slots = {
        "THEME": escape(theme, quote=True), "THEME_VERSION": escape(str(themes[theme]["version"]), quote=True),
        "TITLE": f"{product} · {'主题预览' if preview else '可行性决策'} · {version}",
        "SLIDES": "\n".join(slides), "CSS": (ASSETS / "presentation.css").read_text(encoding="utf-8"),
        "LICENSE": license_text, "REVEAL": reveal, "RUNTIME": (ASSETS / "deck.js").read_text(encoding="utf-8"),
    }
    return re.sub(r"@@([A-Z_]+)@@", lambda m: slots[m[1]], TEMPLATE.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("brief", "model", "evidence", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--theme", default="boardroom", help="视觉主题编号，默认 boardroom 兼容既有命令")
    parser.add_argument("--preview", action="store_true", help="只渲染本次首页与画布，预览页证据编号显示为文本")
    args = parser.parse_args()
    try:
        target = args.output.resolve()
        if target in {p.resolve() for p in (args.brief, args.model, args.evidence)} or ASSETS.resolve() in target.parents:
            raise ValueError("请使用独立的输出路径，以保留输入与安装资源")
        result = render(read(args.brief), read(args.model), read(args.evidence), args.theme, args.preview)
        write_html(args.output, result)
    except (KeyError, ValueError, TypeError, OSError) as error:
        parser.exit(2, f"生成报告失败：{error}\n")
    print(args.output)


if __name__ == "__main__":
    main()
