# bx：从产品想法到可行性报告与 PRD

bx 是一套安装在项目内的 Agent Skills，可由 Codex CLI、Gemini CLI 和 Antigravity 加载，帮助你判断一个产品想法是否值得投入，再把已选定的方向转成可以评审和验收的产品需求文档。

| 技能 | 什么时候用 | 主要工作与交付 |
| --- | --- | --- |
| `bxf` | 有一个想法、发现某个现象、寻找商机，或需要判断是否继续投入 | 逐轮澄清目标，研究市场与竞争，核实证据，测算商业与现金模型；内容定稿后预览并选择主题，再生成带单页九格画布的离线全屏 HTML 报告 |
| `bxp` | 已经选定可行性报告，明确要求编写或修订 PRD | 将报告中的决策转成产品范围、角色与流程、功能需求、异常处理、指标和验收标准，默认交付 `PRD.md` |

典型流程：**提出想法 → 澄清目标 → 调研与测算 → 审阅内容 → 预览并选择主题 → 交付可行性报告 → 明确要求编写 PRD → 审阅 PRD**。

## 环境要求

- 支持项目级 `.agents/skills/` 的 Codex CLI、Gemini CLI 或 Antigravity，且已启用客户端的技能功能。
- macOS、Linux 或 Windows 的 WSL，具备 `sh` 和 Python 3.9+；在线一键安装还需要 `curl`，以及访问 GitHub 和其下载域名的网络。
- 安装和生成报告只需要 Python 标准库。技能内置固定版本的 Reveal.js 及其 MIT 许可证。可选的浏览器排版检查使用 Playwright。
- 开展真实研究时，Agent 需要联网检索或读取你提供的资料，并有项目目录的写入权限。没有检索能力时，可先使用已有材料，但报告须说明证据缺口。
- 查看、翻页和打印最终 HTML 报告需要现代浏览器。报告本身可离线打开。

## 客户端与调用

安装程序统一写入目标项目的 `.agents/skills/bxf/` 和 `.agents/skills/bxp/`。支持该发现目录的客户端读取同一份技能、脚本和报告主题。应在目标项目中启动客户端，或将该项目作为工作区打开。

下表中的提示词和斜杠命令在 Agent 对话中输入。

| 客户端 | 调用 bxf / bxp | 安装后检查 |
| --- | --- | --- |
| Codex CLI | `$bxf …`、`$bxp …` | 可用 `/skills` 查看技能；未发现时重新启动会话 |
| Gemini CLI | `使用 bxf …`、`使用 bxp …` | `/skills reload` 后用 `/skills list` 检查 |
| Antigravity App / CLI | `/bxf …`、`/bxp …`，也可直接点名技能 | CLI 可用 `/skills reload`，App 可开启新对话 |
| Antigravity 独立 IDE | `使用 bxf …`、`使用 bxp …` | 在代理侧栏的 Customizations 中检查技能 |

Gemini CLI 的 `/skills` 用于管理技能；实际任务在普通提示词中点名。激活时按客户端界面完成技能授权。其余客户端也可根据任务描述自动选择相关技能。

若 Gemini CLI 提示工作区未受信任并跳过项目技能，先在客户端的目录信任提示中确认当前项目，再刷新技能列表。这个条件见 [Gemini CLI 目录信任说明](https://geminicli.com/docs/cli/trusted-folders/)。

目录与调用方式依据 2026-11-27 查阅的 [Codex 技能说明](https://learn.chatgpt.com/docs/build-skills)、[Gemini CLI 技能说明](https://geminicli.com/docs/cli/skills/)和 [Antigravity 技能说明](https://antigravity.google/docs/skills)。旧版客户端的发现目录或技能功能可能不同，安装后先检查是否列出 `bxf`、`bxp`。

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

以下示例使用通用的“使用 bxf / bxp”提示词。Codex CLI 中也可直接使用 `$bxf`、`$bxp`，Antigravity App/CLI 可使用 `/bxf`、`/bxp`。单独调用 bxf 可以从想法澄清开始；单独调用 bxp 时，需要当前对话能唯一定位已交付的正式报告，否则技能会询问报告位置。

### 示例一：评估一个产品想法

```text
使用 bxf，我想为小型烘焙店做一个减少临期食材损耗的工具。
先评估上海单店商户是否有付费意愿，我能投入两个人、三个月。
请通过提问帮我明确首个客群、付费方和最先要验证的假设。
工作文件和最终报告放在 reports/bakery-loss/。
```

技能会先澄清足以改变方向的关键问题，再开展研究。根据实际可取得的证据比较机会、竞争和收费方案，计算保守、基准、乐观情景，以及会使建议改变的临界值。方向变化时，受影响的研究和测算也会调整。

它会先提交决策摘要、商业画布草案、关键测算与最大不确定性。审阅后，你可以明确回复：

```text
我确认这版草案，请按当前范围定稿，生成离线 HTML 报告。
```

内容确认后，bxf 会用本次分析的首页和商业画布生成三套两页样张。打开预览，对比「董事会简报」「资本市场路演」「战略研究」，在对话中回复选定的主题。若已在定稿指令中指定主题，直接沿用。

最终报告通常为 `reports/bakery-loss/report.html`，实际以交付路径为准。报告打开即铺满浏览器视口，方向键翻页，F 切换系统全屏，页码常驻。点击九格中的模块可查看关联。章节和页数按实际问题组织，例如一份报告可以用一页说明财务模型，另一份可分成经营结果、资金时序和保本条件三页。工作目录还会保留本次输入与计算结果，方便修订。

### 示例二：根据报告编写 PRD

收到报告后，在当前或新的项目对话中明确指定文件：

```text
使用 bxp，根据 reports/bakery-loss/report.html 编写第一版 PRD。
范围限定为报告推荐的试点，写清核心流程、异常处理、指标和验收标准。
```

默认输出到报告同目录的 `PRD.md`，本例为 `reports/bakery-loss/PRD.md`。你也可以在提示词中指定其他位置或文件名。

`bxp` 也可以使用其他工具制作、且能够读取的可行性报告。报告本身需要说明产品、建议、范围、约束、指标及关键假设，不要求保留上阶段对话。只认可报告不会自动开始编写 PRD，需要明确发出编写指令。

### 示例三：修订现有 PRD

```text
使用 bxp，继续修订 reports/bakery-loss/PRD.md，仍依据 reports/bakery-loss/report.html。
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

python3 -B "$skill_dir/scripts/preview_themes.py" \
  --brief "$skill_dir/assets/example/brief.json" \
  --model "$output_dir/results.json" --evidence "$output_dir/evidence.json" \
  --output-dir "$output_dir/theme-previews"

# 示例明确选择董事会简报。实际任务在用户选定主题后运行。
python3 -B "$skill_dir/scripts/render_report.py" \
  --brief "$skill_dir/assets/example/brief.json" \
  --model "$output_dir/results.json" \
  --evidence "$output_dir/evidence.json" \
  --theme boardroom --output "$output_dir/report.html"
```

打开 `reports/bx-demo/theme-previews/index.html` 切换三套样张，打开 `reports/bx-demo/report.html` 查看选定主题的完整报告。主题标识分别是 `boardroom`、`capital`、`editorial`。[报告制作说明](.agents/skills/bxf/references/slides.md) 包含简报字段、按内容分页方式和验收命令。真实任务使用自己的证据台账、参数和简报，保留来源和数据期间；示例数字与结论不能作为实际经营建议。

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
        │   └── assets/        # 三套视觉主题、离线演示引擎与合成示例输入
        └── bxp/
            ├── SKILL.md
            └── assets/        # PRD 评审模板
```
