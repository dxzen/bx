# 把审阅稿交付为可独立阅读的报告

在草案获得确认后，采用 [HTML5 模板](../assets/report.html)。将 [示例简报](../assets/example/brief.json) 复制到本次分析的工作目录，保留结构，逐项替换为有依据的内容。示例把当前可做的补证、同意试点的条件、扩大投入所需的后续观察分别写明。所有价格和门槛均为合成设定。实际报告用真实产品名、版本、定稿状态和数据期间标识。脚本只依赖 Python 3.9+ 标准库，输出的一个 HTML 文件包含正文、证据、画布、表格、图表、样式和翻页逻辑。

## 复现示例

从本 Skill 目录运行。真实任务把三个输入及输出路径换成本次项目文件。数据口径和模型适用条件见[测算说明](calculation.md)。

```sh
mkdir -p /tmp/product-skill-demo
python3 scripts/research.py assets/example/evidence.csv /tmp/product-skill-demo/evidence.json
python3 scripts/model.py assets/example/model.json /tmp/product-skill-demo/evidence.json /tmp/product-skill-demo/results.json
python3 scripts/render_report.py --brief assets/example/brief.json --model /tmp/product-skill-demo/results.json --evidence /tmp/product-skill-demo/evidence.json --output /tmp/product-skill-demo/report.html
```

## 填写简报

- `decision` 填首页结论、决定性依据、最大不确定性、翻转条件。建议取“推进”“限定范围试点”“补证后决策”或“暂缓”。`analysis` 按影响决策的顺序组织具体论据，每页用唯一英文 `id`、可引用的标题和 `rows` 标签/正文对。内容变长就增页。角色、客群、地区、期间、采购路径、切换成本、行为实验和商业方案取舍都要落实到具体场景。
- `canvas` 的九个短文案分别对应模板中的九格；客户、渠道、付费、价格和成本取自同一模型。用短句点出待验证项，展开论证放在其他页。多边业务分别阐明各方的所得、付出和启动顺序。
- 文本可用 `{{business.payer}}` 或 `{{scenarios.base.summary.peak_cash_need}}` 引用结果 JSON 的标量。数值最多显示两位小数；单位写在标签或句子里，比例字段使用 0 至 1 口径。写 `[[H1]]` 引用台账中的指定编号；渲染器会核对并生成附录页链接。核对每个决定性引文的原文是否支持所在句子的判断，用台账类型说明强度。范围确认可证明谁被选为首批客群，实际订单与回款才可支持已成交与已到账。
- `finance.metrics` 的 `path` 相对于每个情景，例如 `summary.net_revenue`；标签含单位与期间。表格及 `finance.chart` 共用情景结果，计算仅在 Python 模型中进行。条形图选择非负指标；无有效分母的值显示“未能计算”，在 `note` 或对应情景的 `notes` 写明原因。若行业需要新的核算单位，先适配模型和指标标签，再用同一份结果生成表格、图和画布。
- `handoff` 明示已确认范围、付费方、计费、约束、非目标、成功指标与未决事项。给口径变化或用户改判附上决定来源。最后一页 `actions` 写优先实验、对象、责任人、周期或投入、通过与未通过时的行动；明确无样本、分母为零、尚未到账等情况如何处理。
- 证据附录由 `--evidence` 的 `records`、`warnings` 生成。参数、来源和公式由 `--model` 的 `assumptions`、`formulas` 生成。避免只附工作目录中的台账路径而略去来源口径。网页来源保留日期和完整链接，本地文件来源保留可复查的文件名及定位信息。

## 定稿核对

在无网络状态打开 `report.html`。逐页核实标题和页码，用左右键、Page Up/Down、Home/End、按钮和证据链接检查导航。直接打开 `report.html#canvas` 应定位画布。禁用 JavaScript 时正文按文档顺序连续展示。

核对画布和正文的客群、渠道、付款人、月价及履约成本，并抽取至少一个财务指标对照结果 JSON。浏览器打印预览选择 A4 横向并关闭浏览器自带页眉页脚，核对每张幻灯片占一页，长链接、表格数字和画布短句齐全。超长时拆解正文或移入附录，保留一页九格总览。交付实际路径和带该路径的 `$bxp` 调用命令；受权限限制未能核对的项目据实列出。
