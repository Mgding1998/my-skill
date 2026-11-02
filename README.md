# My Skills

用于集中管理个人 Copilot Skills 的仓库。每个 Skill 都是一个可独立安装、调用和维护的能力包；当前仅包含 SUNMI 图标设计 Skill，后续新增的 Skill 将继续收录在统一目录和索引中。

## Skill 索引

| Skill | 状态 | 用途 | 入口 |
|---|---|---|---|
| SUNMI Icon Design | 可用 | 严格按 SUNMI 规范设计、重绘、校正和审查 24×24 图标 | [SKILL.md](./.github/skills/SUNMI-icon-design-skill/SKILL.md) |

新增 Skill 时，在此表追加一行，避免使用彼此重叠或含义模糊的名称。

## SUNMI Icon Design

[`SUNMI-icon-design-skill`](./.github/skills/SUNMI-icon-design-skill/) 用于交付符合 SUNMI 视觉体系的单色 SVG 图标，包括 Line、Fill、Line/Fill 成对图标及图标集审查。

### 核心能力

- 使用固定的 24×24 画布和四类光学盒校正实际图形尺寸
- 以约 1.86–2 px 的主视觉重量统一轮廓
- 分别设计 Line 和 Fill，而不是机械加粗或合并路径
- 检查视觉中心、负空间、黑色面积和小尺寸辨识度
- 输出使用 `currentColor`、透明背景和填充轮廓的生产 SVG
- 校验 SVG 结构、命名、颜色及 Line/Fill 配对

外部参考图只用于提取对象语义、动作、必要识别特征和方向；圆角、线宽、端点、比例、负空间及 Fill 策略必须由 SUNMI 规范决定。

### 调用示例

```text
使用 SUNMI-icon-design-skill，设计一个 24×24 的“文件检验”图标。
需要 Line 和 Fill 两个版本，严格按照 SUNMI 视觉规范和光学盒要求交付。
```

如果提供了参考图，可以这样说明：

```text
使用 SUNMI-icon-design-skill，根据这张参考图提取图标语义，
但不要继承参考图的圆角、线宽和造型风格，最终严格执行 SUNMI 规范。
```

### 校验

```bash
python3 -m unittest discover \
  -s .github/skills/SUNMI-icon-design-skill/scripts \
  -p 'test_*.py' -v

python3 .github/skills/SUNMI-icon-design-skill/scripts/validate_svg.py \
  path/to/icons --require-pairs --strict
```

## 仓库结构

```text
.github/
└── skills/
    ├── SUNMI-icon-design-skill/
    │   ├── SKILL.md
    │   ├── assets/
    │   ├── references/
    │   └── scripts/
    └── <future-skill>/
        ├── SKILL.md
        ├── assets/       # 可选：模板和复用资源
        ├── references/   # 可选：详细规范和领域知识
        └── scripts/      # 可选：校验与自动化脚本
```

每个 Skill 都应保持自包含，不能依赖其他 Skill 目录中的相对文件。

## 新增 Skill

1. 在 `.github/skills/` 下创建独立目录。
2. 添加 `SKILL.md`，并确保 frontmatter 中的 `name` 与目录名完全一致。
3. 在 `description` 中写清触发场景、输入和核心能力，便于 Copilot 正确发现 Skill。
4. 按需添加 `assets/`、`references/` 和 `scripts/`，所有相对链接必须有效。
5. 为可自动验证的约束添加测试或校验脚本。
6. 在本 README 的“Skill 索引”中登记名称、用途、状态和入口。
7. 验证完成后通过标准 Git 流程提交。

可复制以下索引行作为新 Skill 的登记模板：

```markdown
| Skill 名称 | 规划中 / 开发中 / 可用 | 一句话说明主要用途 | [SKILL.md](./.github/skills/<skill-name>/SKILL.md) |
```

## Git 工作流

```bash
git pull --rebase
git status
git add .
git commit -m "Describe the skill change"
git push
```

提交前应确认只包含目标 Skill 的源文件、文档、模板和必要脚本，不提交临时导出、缓存、系统文件或敏感配置。
