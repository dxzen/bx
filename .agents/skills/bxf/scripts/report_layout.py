"""Semantic fragments for a self-contained BXF report, independent of its visual theme."""
import math
import re
import unicodedata
from dataclasses import dataclass
from html import escape, unescape
from itertools import groupby


SCENARIOS = {"conservative": "保守", "base": "基准", "optimistic": "乐观"}
TOKEN = re.compile(r"\{\{([\w.]+)\}\}|\[\[([\w.-]+)\]\]")
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]*")
# Keep interpolations and evidence references intact, including when splitting long prose.
ATOM = re.compile(r"\{\{[\w.]+\}\}|\[\[[\w.-]+\]\]|[A-Za-z0-9]+|\s+|.", re.S)
SENTENCE_END = re.compile(r"([。！？；!?](?:[”’」』）])?(?:\s*\[\[[\w.-]+\]\])*)")
CELLS = {
    "partners": "重要合作伙伴", "activities": "关键业务", "resources": "核心资源",
    "value": "价值主张", "relations": "客户关系", "channels": "渠道通路",
    "segments": "客户细分", "costs": "成本结构", "revenue": "收入来源",
}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"需要有限数值，收到 {value!r}")
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def display(value):
    if value is None:
        return "未能计算"
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("报告含空白文本")
        return value
    return number(value)


def lookup(obj, path):
    """Resolve scalar fields or a model series. Dotted integer indices address a list."""
    for key in path.split("."):
        if isinstance(obj, dict) and key in obj:
            obj = obj[key]
        elif isinstance(obj, list) and re.fullmatch(r"[0-9]+", key) and int(key) < len(obj):
            obj = obj[int(key)]
        else:
            raise ValueError(f"找不到数据字段 {path}")
    return obj


def plain(markup):
    return unescape(re.sub(r"<[^>]+>", "", markup))


def width(text):
    """Conservative line estimate in CJK glyphs, with narrower Latin letters."""
    return sum(1 if unicodedata.east_asian_width(ch) in "WF" else .56 for ch in text)


class Content:
    def __init__(self, model, links, preview=False):
        self.model = model
        self.links = links
        self.preview = preview

    def __call__(self, raw):
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("简报文本必须是非空字符串")
        parts = []
        end = 0
        for match in TOKEN.finditer(raw):
            parts.append(escape(raw[end:match.start()]))
            path, ref = match.groups()
            if path:
                parts.append(escape(display(lookup(self.model, path))))
            else:
                if ref not in self.links:
                    raise ValueError(f"证据编号 {ref} 不在输入的台账内")
                label = escape(ref)
                cite = f'<span class="ref">[{label}]</span>' if self.preview else (
                    f'<a class="ref" href="#{self.links[ref]}" aria-label="查看证据 {label}">[{label}]</a>')
                parts.append(cite)
            end = match.end()
        parts.append(escape(raw[end:]))
        result = "".join(parts)
        if "{{" in result or "[[" in result:
            raise ValueError(f"未解析的标记 {raw!r}")
        return result

    def size(self, raw):
        return width(plain(self(raw)))

    def split(self, raw, limit):
        if self.size(raw) <= limit:
            return [raw]
        terms = SENTENCE_END.split(raw)
        sentences = [a + b for a, b in zip(terms[::2], terms[1::2] + [""])]
        units = []
        for sentence in sentences:
            if not sentence:
                continue
            if not sentence.strip() or self.size(sentence) <= limit:
                units.append(sentence)
                continue
            # A paragraph might have no punctuation. Leave evidence/model tokens indivisible.
            for atom in ATOM.findall(sentence):
                if not TOKEN.fullmatch(atom) and width(atom) > limit:
                    step = max(1, int(limit))
                    units.extend(atom[start:start + step] for start in range(0, len(atom), step))
                else:
                    units.append(atom)
        pieces, current, length = [], "", 0
        for term in units:
            size = self.size(term) if term.strip() else width(term)
            if current.strip() and length + size > limit and term.strip() and not term.lstrip().startswith("[["):
                pieces.append(current)
                current, length = "", 0
            current += term
            length += size
        if current.strip():
            pieces.append(current)
        return pieces


@dataclass(frozen=True)
class Part:
    html: str
    cost: int
    opening: str = ""
    closing: str = ""


def pack(parts, capacity=12):
    """Page breaks only between semantic fragments; each table page retains its header."""
    groups, run, cost = [], [], 0
    for item in parts:
        if run and cost + item.cost > capacity:
            groups.append(run)
            run, cost = [], 0
        run.append(item)
        cost += item.cost
    if run:
        groups.append(run)
    return groups


def join(parts):
    out = []
    for (opening, closing), items in groupby(parts, key=lambda part: (part.opening, part.closing)):
        out.extend([opening, *(p.html for p in items), closing])
    return "".join(out)


def prose(items, content):
    parts = []
    for row in items:
        label = content(row["label"])
        for i, segment in enumerate(content.split(row["text"], 156)):
            text = content(segment)
            heading = label if i == 0 else f'{label}<small class="continuation">（续）</small>'
            parts.append(Part(f'<article class="row"><h3>{heading}</h3><p>{text}</p></article>',
                              max(3, 1 + math.ceil((width(plain(text)) + width(plain(label)) / 2) / 47)),
                              '<div class="rows">', '</div>'))
    return parts


def table_parts(head, body, css):
    if not 2 <= len(head):
        raise ValueError("表格至少需要两列")
    if not body:
        raise ValueError("表格至少需要一条数据")
    if any(len(row) != len(head) for row in body):
        raise ValueError("表格每行的列数必须与表头一致")
    header = "".join(f'<th scope="col">{col}</th>' for col in head)
    opening = f'<div class="table-wrap"><table class="{css}"><thead><tr>{header}</tr></thead><tbody>'
    parts = []
    for label, *cells in body:
        tds = "".join(f"<td>{val}</td>" for val in cells)
        # A wide row predominantly containing numbers costs one line. Longer text consumes more.
        cell_width = 80 / len(head)
        cost = max(1, math.ceil(width(plain(label)) / (36 if css == "compare" else cell_width)),
                   *(math.ceil(width(plain(val)) / cell_width) for val in cells))
        parts.append(Part(f'<tr><th scope="row">{label}</th>{tds}</tr>', cost,
                          opening, '</tbody></table></div>'))
    return parts


def metrics_parts(items, model, content):
    rows = []
    for metric in items:
        values = [escape(display(lookup(model["scenarios"][key], metric["path"]))) for key in SCENARIOS]
        rows.append([content(metric["label"]), *values])
    return table_parts(["指标", *SCENARIOS.values()], rows, "compare")


def bars(spec, model, content):
    values = [lookup(model["scenarios"][name], spec["path"]) for name in SCENARIOS]
    finite = [value for value in values if value is not None]
    for value in finite:
        number(value)
        if value < 0:
            raise ValueError("情景条形图需要非负指标，负值可用表格或趋势图")
    maximum = max(finite, default=0)
    html = [f'<figure class="chart"><figcaption>{content(spec["label"])}</figcaption>']
    for (key, label), value in zip(SCENARIOS.items(), values):
        extent = 100 * value / maximum if value is not None and maximum else 0
        html.append(f'<div class="barrow" data-scenario="{key}"><span>{label}</span>'
                    f'<div class="track" aria-hidden="true"><div class="bar" style="width:{extent:.4f}%">'
                    f'</div></div><output>{display(value)}</output></div>')
    return Part("".join(html) + "</figure>", 5)


def trend(spec, model, content):
    series = lookup(model, spec["path"])
    if not isinstance(series, list) or not series:
        raise ValueError("趋势图需要非空的模型序列")
    pairs = [(lookup(row, spec["x"]), lookup(row, spec["y"])) for row in series]
    for x, y in pairs:
        number(x)
        number(y)
    if any(x1 >= x2 for (x1, _), (x2, _) in zip(pairs, pairs[1:])):
        raise ValueError("趋势图横坐标须严格递增")
    x_label, y_label = content(spec["x_label"]), content(spec["y_label"])
    label = content(spec["label"])
    low_y, high_y = min(0, min(y for _, y in pairs)), max(0, max(y for _, y in pairs))
    # Give a constant zero series a valid scale and keep its actual values visible.
    high_y = high_y if high_y > low_y else low_y + 1
    min_x, max_x = pairs[0][0], pairs[-1][0]
    left, right, top, bottom = 102, 904, 17, 139

    def px(x):
        return left + (x - min_x) / (max_x - min_x) * (right - left) if max_x > min_x else (left+right)/2

    def py(y):
        return bottom - (y - low_y) / (high_y - low_y) * (bottom - top)

    desc = "，".join(f"{number(x)}：{number(y)}" for x, y in pairs)
    html = [f'<figure class="trend"><figcaption>{label} · {y_label}</figcaption>',
            f'<svg viewBox="0 0 940 182" role="img" aria-label="{escape(plain(label), quote=True)}">'
            f'<title>{escape(plain(label))}</title><desc>{escape(plain(x_label))} / {escape(plain(y_label))} · {desc}</desc>']
    for y in sorted({low_y, 0, high_y}):
        pos = py(y)
        html.append(f'<line class="grid-line" x1="{left}" x2="{right}" y1="{pos:.1f}" y2="{pos:.1f}" />'
                    f'<text class="axis-label" x="{left-10}" y="{pos+4:.1f}" text-anchor="end">{number(y)}</text>')
    points = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in pairs)
    html.append(f'<polyline class="series-line" points="{points}" fill="none"/>')
    tick_indices = {round(i*(len(pairs)-1)/5) for i in range(6)}
    for i, (x, y) in enumerate(pairs):
        html.append(f'<circle class="point" cx="{px(x):.1f}" cy="{py(y):.1f}" r="3">'
                    f'<title>{escape(plain(x_label))} {number(x)} · {number(y)}</title></circle>')
        if i in tick_indices:
            html.append(f'<text class="axis-label" x="{px(x):.1f}" y="{bottom+19}" text-anchor="middle">{number(x)}</text>')
    html.append(f'<text class="axis-label" x="{right}" text-anchor="end" y="180">{escape(plain(x_label))}</text></svg></figure>')
    return Part("".join(html), 6)


def page_parts(spec, model, content):
    parts = []
    if "metrics" in spec:
        parts.extend(metrics_parts(spec["metrics"], model, content))
    if "table" in spec:
        table = spec["table"]

        def cell(value):
            return content(value) if isinstance(value, str) else escape(display(value))

        headings = [cell(v) for v in table["headers"]]
        rows = []
        for raw in table["rows"]:
            if len(raw) != len(headings):
                raise ValueError("表格每行的列数必须与表头一致")
            limit = max(36, 300 // max(len(headings), 1))
            columns = [[content(p) for p in content.split(value, limit)] if isinstance(value, str)
                       else [cell(value)] for value in raw]
            for i in range(max(len(c) for c in columns)):
                # Repeat the row label on a continuation. Other cells retain their order.
                rows.append([col[i] if i < len(col) else (col[0] + "（续）" if j == 0 else "")
                             for j, col in enumerate(columns)])
        parts.extend(table_parts(headings, rows, "data-table"))
    if "chart" in spec:
        parts.append(bars(spec["chart"], model, content))
    if "trend" in spec:
        parts.append(trend(spec["trend"], model, content))
    if "rows" in spec:
        parts.extend(prose(spec["rows"], content))
    if not parts:
        raise ValueError(f'{spec.get("title", "内容页")} 缺少论据、数据表或图表')
    return parts
