# 从分析稿到离线报告

## 内容与主题分别保存

分析稿记录本次决策、证据和推理。按要回答的问题组织章节，每页用一句有意义的标题。预览和正式报告读取**同一份**简报、计算结果、证据台账。换主题只改命令的 `--theme`。工作目录里保留三份输入以及生成的 HTML。选择主题的消息可以记入工作目录的决策记录。

三套主题共享内容结构。**董事会简报**（`boardroom`）使用暖白、深蓝和分栏摘要，适合投入决策。**资本市场路演**（`capital`）使用深底、亮色数字及横向论据，适合演示规模、趋势和现金。**战略研究**（`editorial`）使用浅灰、靛色、衬线标题及不对称栏，适合比较假设和证据。用 [主题清单](../assets/themes.json) 记录标识和版式版本。颜色、字体、间距、情景色、九格位置和续页样式统一来自 [presentation.css](../assets/presentation.css)。报告 HTML 保留主题版本，复现历史样稿应使用当时的 skill 版本。

## 实际生成顺序

按[测算说明](calculation.md)得到 `evidence.json` 和 `results.json`。将审阅稿放在同一工作目录的 `brief.json`。下面的命令假定从项目根目录运行；实际任务从当前加载的 `SKILL.md` 路径确定 `skill_dir`，并以本次项目或用户指定的目录作为输出位置。工作目录不同时使用绝对路径。

```sh
skill_dir=".agents/skills/bxf"
out="reports/bx-demo"
python3 -B "$skill_dir/scripts/preview_themes.py" \
  --brief "$out/brief.json" --model "$out/results.json" --evidence "$out/evidence.json" \
  --output-dir "$out/theme-previews"
```

提交 `theme-previews/index.html`，用户可在同一页切换主题、首页和画布，也能单独打开两页样张。这个命令只生成预览。用户在对话中选定后再运行正式生成命令。这里以用户选择董事会简报为例。

```sh
python3 -B "$skill_dir/scripts/render_report.py" \
  --brief "$out/brief.json" --model "$out/results.json" --evidence "$out/evidence.json" \
  --theme boardroom --output "$out/report.html"
```

已有直接调用脚本的程序可沿用旧参数，默认使用 `boardroom`。交互流程以用户选定的主题显式传参。也可加 `--preview` 单独生成指定主题的两页预览。正式文件内嵌样式、字体栈、本地分发的 Reveal.js 及 MIT 许可。无 CDN、外部字体或服务器依赖。

## 简报结构

用[可运行的简报](../assets/example/brief.json)查看完整示例。正文文字允许 `{{business.payer}}`、`{{scenarios.base.summary.peak_cash_need}}` 等标量绑定，数组可用数字下标。单位随文给出。`[[H1]]` 引用本次台账，正式报告可由此跳转附录。生成脚本对输入文字做转义。

- `decision` 包含 `title`、`verdict`、`rows`。每条 `row` 是一个 `{label, text}` 论点。收紧首页，写明当前建议、决定性条件和会令建议改变的观察。可选 `metrics` 收一至两个 `{label, value, unit}`，用于最影响决策的指标。
- `chapters` 是有序章节，每项有 `id`、`label` 和有序的 `pages`。页有唯一的 `id`、`title`，可带正文、表格或图。旧简报的 `analysis` 页列表仍受支持。研究中出现新问题时可用文字论点直接成页。想改变画布位置时，在章节序列中放入 `{"id":"canvas"}`。
- `canvas` 填九格与 `note`。每格留一句核心判断，详细数字和行为依据放回相应章节或通过证据编号引用。无证据的结论写明待验证。预览和正式稿的画布均占一个演示页。
- `finance.pages` 是有序财务页列表。单问资金上限时可只填一页指标。需要解释经营和现金的差别时可写三页，依次用表格对照三个情景、用折线说明最低现金月份、用临界价格描述建议翻转条件。这些页型也能直接放进任意章节。旧简报的 `finance.metrics`、`finance.chart` 仍可渲染。
- `handoff` 记录已确定范围、约束、成功指标和未决事项。`actions` 交代优先实验、负责人、投入、通过条件和停止条件。证据、模型参数和公式附录从台账、模型生成。

| 页内材料 | 字段 | 用途 |
| --- | --- | --- |
| 论据 | `rows: [{label, text}]` | 自由分析、备选方案、反证、访谈与行动。 |
| 情景指标 | `metrics: [{label, path}]` | `path` 相对于各个情景，如 `summary.net_revenue`。标签给出单位与期间。 |
| 自由表格 | `table: {headers, rows}` | 列标题数组与同宽的二维数据。适合比较采购流程或非订阅模型结果。 |
| 情景条形图 | `chart: {label, path}` | 三种情景的非负指标，金额可带单位。 |
| 趋势图 | `trend: {label, path, x, y, x_label, y_label}` | `path` 指向模型中的时间序列。可含负值，横坐标递增；单位写入轴标题。 |
| 适用边界 | `note` | 表格、趋势或结论同时须读的口径、期间与引用。 |

如果固定的订阅机制不适用，按实际业务建模，用自由表格、趋势或论据解释结果。不要为凑三种图而补设事实。主题和页型保持独立，主题名不写入正文。

## 制作与验收

在浏览器打开报告，左右或上下方向键翻页，Home/End 跳到首末，F 进入或退出系统全屏。页码与进度随当前页更新。`report.html#canvas` 可直达九格，点选或用 Tab、Enter 选择某格查看关联模块，Escape 清除高亮。窄屏允许纵向阅读。关闭 JavaScript 后全文按顺序展示。打印选 A4 横向并关闭系统页眉页脚。

每份报告检查首页、九格、最密的表格及至少一条实际引文。表头、单位、数字和结论应能一并读到。检查当前视口的正文边界，超长表可以续页并重复表头，长分析按语义另开页。正式交付前确认关键数值能从同一份模型复算。

维护主题时，用同一份示例输入，在同一浏览器、字体和视口下复核首页、画布和财务页的截图。对有意更改的版式更新主题版本并保留获认可的基准样张。不同项目以正文完整和可读为验收条件。

安装了 Playwright 和 Chromium 的环境可运行可选检查。给出本次报告路径和独立的截图目录。它以固定视口打开本地文件，检验分页、导航、内容边界和打印。审核基准后，将其保存在单独目录。只有在输入、浏览器、系统字体和视口相同的视觉回归检查中才使用 `--baseline`。

```sh
node "$skill_dir/scripts/check_slides.cjs" "$out/report.html" "$out/checks/boardroom"
# 有已认可的基准图时，在上一条命令末尾加 --baseline /path/to/approved/boardroom
```
