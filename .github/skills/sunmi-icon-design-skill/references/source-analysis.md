# Figma 源文件分析

## 范围与方法

- 图标库来源：[Untitled 图标设计稿](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=0-1)
- 当前图标盒来源：[商米统一图标库节点 `24766:3401`](https://www.figma.com/design/PqRlehbKFDl2GnT5oBdcra/%E5%95%86%E7%B1%B3%E7%BB%9F%E4%B8%80%E5%9B%BE%E6%A0%87%E5%BA%93?node-id=24766-3401&m=dev)
- 页面：`Page 1`，节点 `0:1`
- 初始分析日期：2026-10-23；图标盒修订日期：2026-11-02
- 方法：
  - 读取页面完整节点树并按目录行清点图标
  - 导出 Weather、Editor、Arrows 三个分类板进行视觉检查
  - 对 11 个类别中的 22 个代表图标读取设计上下文
  - 检查 18 个代表 SVG 的实际路径数据
  - 查询代表节点的变量绑定
  - 读取新图标盒节点 `24766:3401` 的 metadata、design context、截图和导出 SVG 几何

这里的几何数值来自代表样本，用于描述体系，不代表 2,908 个图标都必须使用相同包围盒。

## 资产结构

页面包含 19 个分类板，所有目录图标实例均为 24×24。按实际目录行清点，共 2,908 个唯一名称：

| 分类 | 图标数 | Line | Fill | 单态/异常 |
|---|---:|---:|---:|---:|
| Weather | 82 | 40 | 40 | 2 |
| User & Faces | 120 | 60 | 60 | 0 |
| System | 331 | 166 | 165 | 0 |
| Others | 134 | 67 | 67 | 0 |
| Map | 170 | 85 | 85 | 0 |
| Media | 248 | 124 | 124 | 0 |
| Logos | 260 | 130 | 130 | 0 |
| Health & Medical | 74 | 37 | 37 | 0 |
| Food | 30 | 15 | 15 | 0 |
| Finance | 162 | 81 | 81 | 0 |
| Editor | 142 | 0 | 0 | 142 |
| Device | 172 | 86 | 86 | 0 |
| Design | 210 | 105 | 105 | 0 |
| Development | 58 | 29 | 29 | 0 |
| Document | 236 | 118 | 118 | 0 |
| Communication | 70 | 35 | 35 | 0 |
| Business | 202 | 101 | 101 | 0 |
| Buildings | 60 | 30 | 30 | 0 |
| Arrows | 147 | 73 | 73 | 1 |
| **合计** | **2,908** | **1,382** | **1,381** | **145** |

变体关系：

- 1,381 组完整 Line/Fill 对，共 2,762 个图标。
- `loading-out-line` 没有对应 Fill。
- Editor 是 142 个不带变体后缀的单态工具/排版符号。
- 其余 3 个“单态”实际是源文件异常，见“数据质量问题”。

## 视觉与几何证据

### 新图标盒

Figma 节点 [`24766:3401`](https://www.figma.com/design/PqRlehbKFDl2GnT5oBdcra/%E5%95%86%E7%B1%B3%E7%BB%9F%E4%B8%80%E5%9B%BE%E6%A0%87%E5%BA%93?node-id=24766-3401&m=dev) 是当前权威的 24×24 图标盒。节点内部展示的是多种居中参考轮廓：

| 类型 | 视觉尺寸 | 画布坐标 |
|---|---:|---|
| 方形/均衡 | 17×17 | `x=3.5, y=3.5` |
| 横向 A | 19×15 | `x=2.5, y=4.5` |
| 横向 B | 20×14 | `x=2, y=5` |
| 竖向 A | 15×19 | `x=4.5, y=2.5` |
| 竖向 B | 14×20 | `x=5, y=2` |
| 圆形 | 19×19 | `cx=12, cy=12, r=9.5` |
| 三角形 | 约 19×16 | 顶点 `(12,3.5)`，底边 `y=19.5` |

节点导出的辅助线使用极细描边，所以原始几何中出现 `18.95×14.95` 等值；计入描边后对应表中的整数视觉尺寸。

新节点修正了旧节点 `18:6006` 的解释：方形、矩形和其他非圆形轮廓不是必须遵守的最大边界，而是宽高比例参考。2026-11-03 的生产规则进一步明确：新绘制的非圆形图标保持所选自然比例，但联合包围盒统一归一到 `17×17 = 289 px²`；不能把不同参考框的较大宽度和高度组合成 20×16 等超面积图形。只有正圆及以正圆为核心外边界的图标严格为 19×19。

### 画布与重量

所有抽样图标均使用 `viewBox="0 0 24 24"`。主视觉重量集中在约 1.859–2 px：

| 样本 | 观察 |
|---|---|
| `account-circle-line` | 外圆约 `2.70468–21.2953`，圆环厚度约 `1.85906` |
| `align-center` | 横线厚度约 `1.85907`，最长横线约 `3.63421–20.3658` |
| `arrow-right-line` | 主杆厚度约 `1.8591`，整体约 `4.56374–19.4363` |
| `add-line` | 主杆厚度 2，整体为 `4–20` |
| `add-fill` | 主杆厚度约 `1.859`，整体约 `5.49328–18.5067` |
| `home-line` | 主体约 `3.63421–20.3658` |
| `map-pin-line` | 尖端到 `y=22.9015`，明显允许语义性下探 |
| `heart-pulse-line` | 脉搏水平线到 `x=1.77515`，允许局部接近边缘 |

大量坐标以约 `0.92953` 为增量，视觉重量常为其两倍。这更像统一缩放/归一化后的结果，不应被当作必须照抄的绘图网格。新图标应匹配可见比例和重量，而不是人为制造长小数。

### Line 构造

- 抽查 SVG 中，“线性”图标不是 SVG stroke，而是一个填充的复合轮廓。
- 环、人物、云、房屋和定位图标通过同一路径中的子路径制造孔洞。
- 实用型直线端点多为方形；有机图形以连续贝塞尔曲线连接。
- 代表样本均可由单个 `<path>` 表达，但单路径是优化目标，不应压过正确性。

### Fill 构造

Fill 是独立重绘，而不是简单把 Line 的空心区域填满：

- `account-circle-fill` 重新分配头像和身体的黑白面积。
- `map-pin-fill` 保留中心孔洞。
- `play-circle-fill` 使用实心圆，同时保留播放三角的可读关系。
- `heart-pulse-fill` 保留脉搏折线形成的关键负空间。
- `arrow-right-fill` 从“主杆 + 开放箭头”变为紧凑实心方向轮廓。
- `home-fill` 移除内部空心，只保留房屋主轮廓。

因此 Line/Fill 应共享语义、方向、视觉中心和总体尺寸，但不要求拓扑一致。

### Line/Fill 共享转角语言

2026-11-02 重新读取原始 Figma 中 6 组 Line/Fill 实例及其实际 SVG 路径，进一步区分“拓扑不同”和“造型性格不同”：

- [`landscape-line` `16:5260`](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=16-5260) / [`landscape-fill` `16:5882`](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=16-5882)：两种变体都用直线段和明确顶点表达三角山峰，属于 Sharp。
- [`gallery-line` `16:5210`](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=16-5210) / [`gallery-fill` `16:5832`](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=16-5832)：两种变体都用连续贝塞尔曲线表达地形，属于 Organic。
- [`home-line` `16:14806`](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=16-14806) / [`home-fill` `16:14958`](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=16-14958)：Fill 移除内部孔洞，但保留与 Line 相同的屋顶轮廓和受控柔化，属于 Soft。
- [`album-line` `16:5075`](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=16-5075) / [`album-fill` `16:5697`](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=16-5697)：黑白关系变化，但主体都保持同心圆形语言。
- [`image-line` `16:5255`](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=16-5255) / [`image-fill` `16:5877`](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=16-5877)：Fill 对山峰顶点做轻微光学缓和，但仍保留明确几何峰、直线坡面和相同方向，没有变成宽圆丘。
- [`slideshow-line` `16:14170`](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=16-14170) / [`slideshow-fill` `16:14677`](https://www.figma.com/design/pyMO9In9eCGPIYz73JhWH3/Untitled?node-id=16-14677)：内部图表的圆形、方形切口与水平直线在两种变体中保持相同几何类别。

因此“不要求拓扑一致”只允许重新组织黑白面积、孔洞和局部细节，不允许无依据地改变对应语义部件的视觉转角类别。成对设计应先为关键部件标记 Sharp、Soft 或 Organic；精确控制点和局部半径可以为光学效果调整，但不能改变主要棱角感、曲直属性、关键顶点顺序或峰谷方向。Mixed 只在同家族 Figma 证据明确支持时使用。

### 单态 Editor 图标

Editor 分类包含对齐、文字样式、列表、表格、输入法、数字和公式等符号。它们：

- 不强制生成 Line/Fill 两套
- 常包含字母、数字或排版符号形态
- 仍遵守 24×24、单色和约 1.86 px 的视觉重量
- 需要特别关注字形识别度，而不是追求与实体图标相同的空心/实心逻辑

### Logo 图标

Logo 分类也提供 Line/Fill 形式，例如 Apple。品牌图标的轮廓由品牌识别决定，不能为了统一圆角或填充比例而改坏商标。该分类应视为受约束的例外。

## 颜色与 SVG 导出

- 代表 SVG 使用黑色 `fill="black"`。
- 代表节点没有返回已绑定的 Figma 变量。
- Figma 导出根节点包含：
  - 固定 `width="24"`、`height="24"`
  - `preserveAspectRatio="none"`
  - `style="display: block;"`
  - `<g id="...">`
  - `<path id="Icon" ... fill="black">`

这些是设计源导出特征，不是推荐的产品交付格式。生产资产应：

- 将黑色替换为 `currentColor`
- 移除 `preserveAspectRatio="none"` 和内联样式
- 保留 `viewBox="0 0 24 24"`
- 避免运行时 stroke、位图、文字和滤镜

## Catalog Board 结构

成对分类板的代表布局：

- 外层宽 1264
- 左右边距 96，内容宽 1072
- Header 为 1072×104
- 图标内容通常从 `y=296` 开始
- Line 区宽 472，Fill 区从 `x=600` 开始，宽 472
- 中间分隔线位于 `x=536`
- 每区两列，列起点 `x=0/252`，单项宽 220
- 图标 24×24，标签从 `x=36` 开始
- 行步进 52，即 24 高 + 28 间距

Editor 单态板：

- 四列，起点 `x=0/276/552/828`
- 单项宽 244
- 同样使用 24×24 图标和 52 的行步进

这些规则适合延续目录展示，但不等同于图标本身的几何规则。

## 数据质量问题

实际节点清点与板上标注不完全一致：

1. Editor 板标注 `140 icons`，实际目录行有 142 个。
2. Arrows 板标注 `146 icons`，实际有 147 个；多出的实例名为 `必填`。
3. Weather 中 `snowflake-line 1` 和 `snowflake-fill 1` 带复制后缀，破坏变体命名。
4. `loading-out-line` 没有对应 Fill，需要确认是有意单态还是漏图。
5. 分类板 Header 的位置不完全统一；Arrows 的 Header 位于内容之后。

因此新增或审查图标时必须自动清点实例、校验名称和配对，不能只相信人工计数徽标。

## 对 Skill 的直接结论

- 默认设计基准是 24×24、单色、透明背景。
- 非圆形以 17×17 的面积为生产基准：参考框只提供自然宽高比，最终联合包围盒等比归一到 289 px²。
- 正圆及以正圆为核心外边界的图标严格为 19×19；所有图形都不得通过修改 `viewBox` 或非等比拉伸伪造尺寸。
- 主重量从约 1.86–2 px 开始，再做光学校正。
- Line 最终使用填充轮廓，但 `fill="currentColor"` 只是技术编码；非微型主体语义部件仍须保持轮廓或线带表达，不能大面积实心化。Fill 需要独立重绘。
- Line/Fill 可以不同构，但对应语义部件必须保持同一视觉转角类别、关键顶点顺序和主要曲直属性。
- 默认生成完整 Line/Fill 对；Editor/排版符号和明确例外可保持单态。
- 命名、配对和真实库存必须自动校验。
- 产品 SVG 必须从 Figma 原始黑色导出规范化为 `currentColor`。
