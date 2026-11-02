# paper-to-markdown

一个 Codex Skill：结合学术论文 PDF 与 LaTeX 源码，生成完整中文 Markdown 和可随文档搬移的本地配图目录。

## 功能

- 翻译并整理摘要、正文、致谢、参考文献和补充材料。
- 对照目标版本保留公式、编号与交叉引用；默认不添加可见的公式块标识符。
- 复制原始配图，为单页 PDF 图生成 PNG 预览，并使用相对路径引用。
- 将多层表头整理为明确列名，保留数值、单位、脚注和指标方向。
- 检查中文标点与加粗边界、数学分隔符、表格列数、图片路径和脚注。

## 安装与使用

将本仓库克隆到 `~/.codex/skills/paper-to-markdown`。若设置了 `CODEX_HOME`，则放到对应目录的 `skills/paper-to-markdown` 下。

在 Codex 中提供论文 PDF 与匹配版本的 LaTeX 源码，然后输入：

```text
使用 $paper-to-markdown，将这篇论文整理为完整中文 Markdown，并复制、引用全部配图。
```

默认交付结构：

```text
论文名-中文/
├── 论文名.md
└── images/
    ├── figure.png
    ├── diagram.pdf
    └── diagram.preview.png
```

也可指定语言、输出位置、图片同级布局或仅修复已有 Markdown。

## 辅助脚本

需要 Python 3.9 或更高版本。PDF 预览另需 Poppler 的 `pdfinfo` 和 `pdftoppm`；普通图片复制与 Markdown 检查只使用 Python 标准库。

```bash
python scripts/prepare_images.py --dest output/images figure.png diagram.pdf
python scripts/check_markdown.py output/paper.md --expect-images 2 --expect-tables 3
python scripts/test_helpers.py
```

如需核对公式编号顺序，可提供 JSON 字符串数组：

```json
["1", "2", "3a", "A.1"]
```

```bash
python scripts/check_markdown.py output/paper.md --expected-tags equation-tags.json
```

脚本不会自动全文翻译或解析任意 LaTeX 工程。翻译和源文核对由 Codex 按技能工作流完成；结构检查通过不代表语义与全部渲染已经验证。图片准备脚本拒绝覆盖不同内容的目标文件，也不会将多页 PDF 静默截取为第一页。

## 文件说明

- [SKILL.md](SKILL.md)：技能入口与工作流程。
- [references/formatting.md](references/formatting.md)：公式、表格、图像和引用规则。
- `agents/openai.yaml`：Codex 界面元数据。
- `scripts/`：图片准备、Markdown 检查和测试。
