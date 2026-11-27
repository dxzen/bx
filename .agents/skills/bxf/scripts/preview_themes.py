#!/usr/bin/env python3
"""Render only the decision and canvas in every theme, and a local comparison page."""
import argparse
from html import escape
from pathlib import Path
import re

from render_report import read, render, write_html


ASSETS = Path(__file__).resolve().parents[1] / "assets"


def preview(brief, model, ledger, directory):
    themes = read(ASSETS / "themes.json")
    options = []
    outputs = {}
    for theme, settings in themes.items():
        filename = f"{theme}.html"
        outputs[filename] = render(brief, model, ledger, theme=theme, preview=True)
        current = "true" if not options else "false"
        options.append(
            f'<a class="choice {escape(theme)}" aria-current="{current}" href="{escape(filename)}">'
            f'<span class="swatch" aria-hidden="true"></span><span><strong>{escape(settings["name"])}</strong>'
            f'<small>{escape(settings["description"])}</small></span></a>'
        )
    template = (ASSETS / "theme-preview.html").read_text(encoding="utf-8")
    fields = {"OPTIONS": "".join(options), "PRODUCT": escape(model["business"]["product"])}
    outputs["index.html"] = re.sub(r"@@(\w+)@@", lambda m: fields[m[1]], template)
    for filename, contents in outputs.items():
        write_html(directory / filename, contents)
    return directory / "index.html"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("brief", "model", "evidence", "output-dir"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    try:
        inputs = [args.brief, args.model, args.evidence]
        reserved = {args.output_dir / name for name in ("index.html", *(key + ".html" for key in read(ASSETS/"themes.json")))}
        if {path.resolve() for path in reserved} & {path.resolve() for path in inputs}:
            raise ValueError("预览目录内的输出会覆盖输入文件")
        path = preview(*(read(path) for path in inputs), directory=args.output_dir)
        print(path)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f"生成预览失败：{error}\n")


if __name__ == "__main__":
    main()
