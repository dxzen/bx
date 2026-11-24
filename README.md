# bx：从产品想法到可行性报告与 PRD

bx 是一套安装在项目内的 Codex 技能，帮助你判断一个产品想法是否值得投入，再把已选定的方向转成可以评审和验收的产品需求文档。

| 技能 | 什么时候用 | 主要工作与交付 |
| --- | --- | --- |
| `bxf` | 有一个想法、发现某个现象、寻找商机，或需要判断是否继续投入 | 逐轮澄清目标，研究市场与竞争，核实证据，测算商业与现金模型；草案经确认后，生成包含九格商业画布的离线 HTML 决策报告 |
| `bxp` | 已经选定可行性报告，明确要求编写或修订 PRD | 将报告中的决策转成产品范围、角色与流程、功能需求、异常处理、指标和验收标准，默认交付 `PRD.md` |

典型流程：**提出想法 → 澄清目标 → 调研与测算 → 审阅草案 → 确认可行性报告 → 明确要求编写 PRD → 审阅 PRD**。

## 环境要求

- 支持项目级 `.agents/skills/` 的 Codex。其他 Agent 需自行确认其技能目录及调用方式。
- macOS、Linux 或 Windows 的 WSL，具备 `sh` 和 Python 3.9+；在线一键安装还需要 `curl`，以及访问 GitHub 和其下载域名的网络。
- Python 脚本和安装程序均只使用标准库，无需安装 pip、npm 包或 Git。
- 开展真实研究时，Agent 需要联网检索或读取你提供的资料，并有项目目录的写入权限。没有检索能力时，可先使用已有材料，但报告须说明证据缺口。
- 查看、翻页和打印最终 HTML 报告需要现代浏览器。报告本身可离线打开。

Codex 会从项目的 `.agents/skills/` 发现技能；安装后在目标项目中打开 Codex，若技能没有出现，重启 Codex。目录发现和刷新规则见 [Codex 官方技能说明](https://learn.chatgpt.com/docs/build-skills)。

## 一键安装

在**需要使用 bx 的项目根目录**执行：

```sh
curl -fsSL https://raw.githubusercontent.com/dxzen/bx/master/install.sh | sh
```

命令从 [dxzen/bx](https://github.com/dxzen/bx) 的 `master` 分支下载技能，安装结果为：

```text
你的项目/
└── .agents/
    └── skills/
        ├── bxf/
        └── bxp/
```

安装包含两个技能的全部脚本、模板、示例和参考资料。技能仅安装到目标项目，不会写入全局技能目录，也不会修改项目现有的 `README.md`、`AGENTS.md` 或其他技能。

也可以指定另一个已存在的项目目录，路径中有空格时保留引号：

```sh
curl -fsSL https://raw.githubusercontent.com/dxzen/bx/master/install.sh | sh -s -- --project "/path/to/my project"
```

该公开安装命令需要仓库 `master` 分支中已存在本 README 对应的 `install.sh` 和 `.agents/skills/`；私有仓库或尚未发布时，使用下面的本地安装方式。

### 从本地仓库安装

如果你已克隆或下载 bx，可以直接从本地副本安装，无需访问网络。进入目标项目后执行，两个路径都填写 **bx 仓库根目录**：

```sh
sh /path/to/bx/install.sh --source /path/to/bx
```

也可以在任意目录执行：

```sh
sh /path/to/bx/install.sh --source /path/to/bx --project /path/to/your-project
```

### 重复安装与更新

| 目标项目的状态 | 默认行为 |
| --- | --- |
| 两个技能都不存在 | 安装两个技能 |
| 同名技能内容相同 | 跳过相同技能，补装缺失技能 |
| 任一同名技能内容不同 | 报错停止，本次不安装任何技能 |
| 使用 `--force` | 跳过相同技能，将内容不同的同名技能备份后替换，并补装缺失技能 |

从 GitHub 更新到 `master` 分支的当前版本：

```sh
curl -fsSL https://raw.githubusercontent.com/dxzen/bx/master/install.sh | sh -s -- --force
```

从本地副本更新：

```sh
sh /path/to/bx/install.sh --source /path/to/bx --force
```

备份保存在目标项目的 `.agents/backups/bx-日期时间-随机后缀/` 下，原有 `bxf/`、`bxp/` 按实际被替换的情况保存。需要恢复时，先移走当前同名技能，再将备份中的技能目录放回 `.agents/skills/`。更新不会修改已有报告或 PRD。

安装程序会在写入技能前检查资源完整性和同名冲突；替换阶段出现可捕获的错误时会尝试恢复原有技能。安装位置及同名技能须为普通目录，符号链接请先自行处理。

查看全部安装参数：

```sh
curl -fsSL https://raw.githubusercontent.com/dxzen/bx/master/install.sh | sh -s -- --help
```

## 使用说明

以下 `$bxf`、`$bxp` 示例是**发送给 Codex 的提示词**，不在终端中执行。单独发送 `$bxf` 可以从想法澄清开始；单独发送 `$bxp` 时，需要当前对话能唯一定位已交付的正式报告，否则技能会询问报告位置。

### 示例一：评估一个产品想法

```text
$bxf 我想为小型烘焙店做一个减少临期食材损耗的工具。
先评估上海单店商户是否有付费意愿，我能投入两个人、三个月。
请通过提问帮我明确首个客群、付费方和最先要验证的假设。
工作文件和最终报告放在 reports/bakery-loss/。
```

技能会先澄清足以改变方向的关键问题，再开展研究。根据实际可取得的证据比较机会、竞争和收费方案，计算保守、基准、乐观情景，以及会使建议改变的临界值。方向变化时，受影响的研究和测算也会调整。

它会先提交决策摘要、商业画布草案、关键测算与最大不确定性。审阅后，你可以明确回复：

```text
我确认这版草案，请按当前范围定稿，生成离线 HTML 报告。
```

最终报告通常为 `reports/bakery-loss/report.html`，实际以交付路径为准。报告包括建议、证据、九格商业画布、情景测算、关键假设和优先验证实验；工作目录还会保留本次输入与计算结果，方便修订。

### 示例二：根据报告编写 PRD

收到报告后，在当前或新的项目对话中明确指定文件：

```text
$bxp 根据 reports/bakery-loss/report.html 编写第一版 PRD。
范围限定为报告推荐的试点，写清核心流程、异常处理、指标和验收标准。
```

默认输出到报告同目录的 `PRD.md`，本例为 `reports/bakery-loss/PRD.md`。你也可以在提示词中指定其他位置或文件名。

`bxp` 也可以使用其他工具制作、且能够读取的可行性报告。报告本身需要说明产品、建议、范围、约束、指标及关键假设，不要求保留上阶段对话。只认可报告不会自动开始编写 PRD，需要明确发出编写指令。

### 示例三：修订现有 PRD

```text
$bxp 继续修订 reports/bakery-loss/PRD.md，仍依据 reports/bakery-loss/report.html。
这版只覆盖一家门店试点，暂不做跨店调拨。
请检查受影响的流程、指标和验收标准，并标记仍待确认的问题。
```

## 在终端复现附带示例

这组命令验证证据整理、商业测算和 HTML 报告生成能否运行。它只处理随包提供的**合成示例数据**，不执行真实市场调研。附带模型适用于按月计费的订阅业务，其他商业机制须按实际情况另建或调整 Python 模型，详见 [测算说明](.agents/skills/bxf/references/calculation.md)。

在已安装技能的项目根目录执行：

```sh
skill_dir=".agents/skills/bxf"
output_dir="reports/bx-demo"

python3 -B "$skill_dir/scripts/research.py" \
  "$skill_dir/assets/example/evidence.csv" "$output_dir/evidence.json"

python3 -B "$skill_dir/scripts/model.py" \
  "$skill_dir/assets/example/model.json" "$output_dir/evidence.json" "$output_dir/results.json"

python3 -B "$skill_dir/scripts/render_report.py" \
  --brief "$skill_dir/assets/example/brief.json" \
  --model "$output_dir/results.json" \
  --evidence "$output_dir/evidence.json" \
  --output "$output_dir/report.html"
```

完成后用浏览器打开 `reports/bx-demo/report.html`，查看报告与商业画布。真实任务使用自己的证据台账、参数和简报，保留来源和数据期间；示例数字与结论不能作为实际经营建议。

## 卸载

在目标项目中删除 `.agents/skills/bxf/` 和 `.agents/skills/bxp/` 即可。确认不再需要旧版本后，可单独删除 `.agents/backups/` 中对应的 `bx-*` 备份目录。报告、PRD 和其他技能由你按需保留。

## 仓库结构

```text
bx/
├── README.md
├── install.sh
└── .agents/
    └── skills/
        ├── bxf/
        │   ├── SKILL.md
        │   ├── scripts/       # 证据清洗、情景测算、报告生成
        │   ├── references/    # 研究方法、测算口径、报告制作
        │   └── assets/        # HTML 模板与合成示例输入
        └── bxp/
            ├── SKILL.md
            └── assets/        # PRD 评审模板
```
