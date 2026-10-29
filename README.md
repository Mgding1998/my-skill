# My Skills

个人使用的 Copilot Skills 仓库。

## Icon Design

[`icon-design`](./.github/skills/icon-design/SKILL.md) 用于设计、补齐、重绘和审查 24×24 单色 SVG 图标，支持：

- Line/Fill 成对设计
- 方形、竖向、横向和圆形光学盒校正
- 视觉重量与多尺寸检查
- SVG 结构、颜色、命名和变体配对校验
- Figma 图标库分析、设计简报与审查报告模板

仓库中的 [`icons/`](./icons/) 保存已完成和用于验证设计规范的图标资产；[`.vscode/mcp.json`](./.vscode/mcp.json) 提供工作区 Figma MCP 配置。

### 使用方式

将本仓库中的 `.github/skills/icon-design/` 复制到目标项目的同一位置，然后在 Copilot Chat 中输入：

```text
使用 icon-design skill，设计一个 24×24 的“文件检验”图标，
需要 Line 和 Fill 版本，并按光学盒校正实际大小。
```

### 校验

```bash
python3 .github/skills/icon-design/scripts/validate_svg.py path/to/icons --require-pairs --strict
python3 -m unittest discover -s .github/skills/icon-design/scripts -p 'test_*.py' -v
```
