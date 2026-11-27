---
name: 禾链智配
description: 深海蓝调度与明亮冰灰业务界面组成的果蔬集采履约工作区
colors:
  primary: "#365ee9"
  primary-hover: "#718df1"
  primary-active: "#294bc2"
  primary-tint: "#eef2fe"
  navigation: "#111f35"
  navigation-active: "#263e65"
  canvas: "#f5f7fa"
  surface: "#ffffff"
  text: "#182c46"
  muted: "#697b91"
  line: "#e5eaf2"
  screen-canvas: "#09172b"
  screen-surface: "#0e213a"
  screen-heading: "#112840"
  screen-line: "#213b59"
  screen-text: "#b3c8e2"
  screen-muted: "#8da8c7"
  screen-highlight: "#e9f3ff"
  flow: "#49c9c0"
  warning: "#e5ba79"
  source-background: "#fff5dc"
  source-text: "#8a631e"
typography:
  headline:
    fontFamily: "'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"
    fontSize: "27px"
    fontWeight: 700
    letterSpacing: "-0.7px"
  title:
    fontFamily: "'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"
    fontSize: "16px"
    fontWeight: 600
  body:
    fontFamily: "'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"
    fontSize: "14px"
    lineHeight: 1.8
  label:
    fontFamily: "'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"
    fontSize: "12px"
  metric:
    fontFamily: "'Segoe UI', 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif"
    fontSize: "31px"
rounded:
  tag: "4px"
  screen: "7px"
  control: "8px"
  choice: "10px"
  result: "11px"
  panel: "12px"
spacing:
  compact: "8px"
  control: "12px"
  mobile: "16px"
  screen: "18px"
  panel: "22px"
  section: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "8px 15px"
    height: "33px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.surface}"
  button-primary-active:
    backgroundColor: "{colors.primary-active}"
    textColor: "{colors.surface}"
  button-primary-plain:
    backgroundColor: "{colors.primary-tint}"
    textColor: "{colors.primary}"
    rounded: "{rounded.control}"
    padding: "8px 15px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
    padding: "22px"
  screen-panel:
    backgroundColor: "{colors.screen-surface}"
    rounded: "{rounded.screen}"
  source-tag:
    backgroundColor: "{colors.source-background}"
    textColor: "{colors.source-text}"
    rounded: "{rounded.tag}"
    padding: "2px 6px"
  navigation-active:
    backgroundColor: "{colors.navigation-active}"
    textColor: "{colors.surface}"
    rounded: "{rounded.screen}"
    padding: "11px 13px"
---

# Design System: 禾链智配

## Overview

**Creative North Star: "深海蓝业务调度中心"**

已获用户确认的高科技业务后台，以深海蓝建立导航和调度氛围，以明亮冰灰承载采购比较、现场作业、品质记录和对账。科技感来自有层次的信息、可追溯的数量及能进入业务明细的可视化；大屏与日常工作区属于同一系统，但使用不同的明暗表面。

本轮根据用户对信息堆叠的反馈，改为单一主任务优先。首页直接展示待办，采购先展示可比较结果，次要条件、费用、证据和历史按需展开。组件继续沿用 Vue、Element Plus 和现有业务接口。

**Key Characteristics:**

- 深海蓝导航与调度大屏，冰灰画布与白色业务容器。
- 靛蓝主操作、青绿履约进度、琥珀异常与来源提示。
- 减少同时出现的面板，使用对齐的列表与等宽数字比较数量、金额。
- 桌面主区域明确，手机围绕当前任务重排。

## Colors

前置令牌记录实际复用色值；各视图的局部色阶服务于同一明暗关系，不构成新的品牌色。

### Primary

- **操作靛蓝**（`primary`）：用于主按钮、可操作链接和选中状态；悬停及按下使用对应的 `primary-hover`、`primary-active`。
- **导航选中蓝**（`navigation-active`）：深色侧栏上的当前页面，配白色文字及图标。

### Secondary

- **履约青绿**（`flow`）：大屏发运、验收和进度提示；业务页按相同语义使用青绿色阶。
- **协同琥珀**（`warning`）：大屏缺口与待处理金额等需要关注的事项。
- **来源浅金**（`source-background` / `source-text`）：明确“演示参数”“样本估算”“整批实称”等证据范围，不充当装饰标签。

### Neutral

- **深海导航**（`navigation`）与**夜航画布**（`screen-canvas`）：分别承载工作区导航与全屏调度。
- **冰灰画布**（`canvas`）、**白色表面**（`surface`）、**细分隔线**（`line`）：承载日常录入、采购和账务。
- **业务墨蓝**（`text`）与**辅助灰蓝**（`muted`）：区分正文与说明。
- 大屏使用 `screen-surface`、`screen-heading`、`screen-line` 分层，以 `screen-highlight` 突出指标，`screen-text` 与 `screen-muted` 承载信息。

**The Evidence Rule.** 颜色始终配合文字说明状态与来源，演示、估算和实际记录在关联明细中持续可辨。

## Typography

**Display Font / Body Font:** Segoe UI，依次回退 Microsoft YaHei UI、Microsoft YaHei 和系统无衬线。以全局升级样式为基准；调度屏保留局部中文无衬线声明，不要求下载字体才能使用。

**Character:** 清晰、稳定、适合中文业务表单。数量、金额和时钟采用 `font-variant-numeric: tabular-nums`，不另引入装饰性数字字体。

### Hierarchy

- **Headline:** 桌面页面标题采用 `headline`；手机缩为（25px）。
- **Title:** 常规面板标题采用 `title`；大屏面板标题通常为（14px），大屏地图标题为（16px）。
- **Body:** 页面介绍与常规控件基础为（14px），介绍行高（1.8），说明区域最大宽度（78ch）；密集任务与记录文字主要为（12–13px）。表格依照现有组件保持紧凑。
- **Label:** 辅助标签、单位和来源以（12px）为基准；导航主项为（13px）。不将所有辅助文字扩大到正文尺寸。
- **Metric:** 常规指标为（31px），手机为（25px）；调度 KPI 为（27px），手机为（23px），交付覆盖值为（32px）。称重预览有局部强调值（49px），不推广为全站指标标准。

**The Numeric Context Rule.** 主数值与单位保持相邻，比例、数量、报价与实付金额保留各自名称和依据。

## Layout

2026-11-27 的布局修正优先于早期密集大屏和三栏采购方案。

- 工作区侧栏宽224px，折叠76px；低频模块分组折叠，只展开当前业务组。顶部栏64px，移动端60px，减少重复入口和信息。
- 常规业务页最大宽1600px，桌面水平留白38px。每页一个主操作、一个主要工作区域；辅助信息不与主任务争用同等面积。
- 首页采用一行简要摘要、待处理/交付/异常切换队列。取消大横幅、重复入口卡和默认事件流；业务动态通过抽屉查看。
- 采购采用短条件栏与同列比较结果。更多条件、单批采购详情、称重依据、所选批次对比图分别按需打开。未匹配批次默认折叠。
- 调度屏采用地图主区与一个可切换的异常/缺口/任务侧栏。交付明细和动态进入抽屉，取消左右多面板和底部重复列表。地图真实坐标、边界与业务关联语义保持一致。
- 作业页先展示任务队列，点击后打开任务抽屉。集采单按待承接、已承接和全部品项切换；称重历史默认收起。操作和证据均保留明确入口。
- 900px以下导航为抽屉；760px以下采购结果转成紧凑记录、条件为两列，首页快捷入口按需打开；手机作业直接显示队列，不把详情置于队列前方。700px以下大屏地图约410px，任务侧栏独立约350px，避免整页无限堆叠。

## Elevation & Depth

业务容器主要依靠白色表面、细描边和留白分层；调度屏主要依靠深蓝色阶及细边框建立深度。地图点位浮层使用局部阴影（`0 12px 28px #0715274d`）。顶部栏使用半透明白色与背景模糊（12px），移动导航使用遮罩分隔前后景。阴影不应覆盖所有卡片。

交互反馈保持短促：Element Plus 按钮沿用（0.1s）状态过渡，手机侧栏位移为（0.2s）。遵从 `prefers-reduced-motion`；动画不承担唯一的信息表达。

## Shapes

常规面板圆角（12px），按钮与输入框基础圆角（8px），用途选择块（10px），货源与任务结果卡（11px），大屏面板（7px），来源标签（4px）。以完整矩形、细边框和克制圆角表达业务秩序；进度条及数量条采用可读的连续条形。图标使用现有 Element Plus 图标，不以图标替代关键业务名称。

## Components

### Buttons

主按钮使用操作靛蓝与白字，基础内边距（8px 15px）、最小高（33px）；大按钮最小高（43px）。次要操作沿用 Element Plus plain/link 变体。手机常规实体按钮最小高（40px），当前任务操作最小高（41px）。保留加载和禁用状态，提交文案描述业务结果。原生控件使用全局可见焦点描边，Element Plus 按钮保留组件自身焦点样式。

### Chips

来源标签为浅金底与深金文字，紧凑圆角及内边距；采购证据行采用（12px）文字。状态标签同时显示可读名称。筛选与页签通过底色、边框或下划线及文字共同区分选中状态。

### Cards / Containers

白色业务面板使用细分隔线、（12px）圆角，标题区内边距（19px 22px），内容区约（22px）。任务卡、用途选择和采购结果各有可见选中描边；整卡可操作时保留键盘焦点。大屏面板使用深色标题条及蓝灰细边框，避免把每个小数据都做成独立卡片。

### Inputs / Fields

沿用 Element Plus 表单、选择器、日期及数量输入，浅色业务页使用白色填充和细描边，大屏筛选采用深蓝填充。输入标签、单位、范围与错误文案相邻；手机输入与选择器最小高（38px）。实际称重、估算参数和报价字段应保留各自语义，提交前展示记录范围与结果预览。

### Navigation

深海蓝侧栏按业务分组；主项（13px）、最小高（42px），选中为实心蓝，悬停为更浅深蓝。折叠保留图标与标题提示，手机以菜单按钮打开抽屉，遮罩关闭；当前业务标题保留在顶部栏。业务消息从右侧抽屉进入关联事项。

### Interactive Business Views

地图点位选择联动业务浮层与站点筛选；地图模式可为天地图或行政区概览，持续展示模式、点位依据和关系图例。连线表达履约业务关联；不代表道路路线或车辆定位。KPI、缺口、异常及任务条目进入对应业务记录或后续操作。采购数量换算保留投入、净量、单价和称重依据的关联；手机保留完整任务步骤。

大屏结构与头部素材参考 [HalseySpicy/Geeker-Admin](https://github.com/HalseySpicy/Geeker-Admin) 的 dataScreen（MIT）。保留仓库 `vendor/geeker-admin` 内的原始结构、来源说明及许可证；适配沿用现有 Vue / Element Plus / Pinia / ECharts 依赖体系。

## Do's and Don'ts

### Do:

- **Do** 在日常业务页使用冰灰画布和明亮容器，在调度屏使用深海蓝分层。
- **Do** 让指标、点位、异常和任务通向关联记录或可执行动作。
- **Do** 保留单位、证据来源、演示标记、同步状态和空状态说明。
- **Do** 按手机任务顺序重排主区域，并保留输入标签和提交步骤。
- **Do** 使用系统中文无衬线与等宽数字特性，保持标题、正文、标签和指标层级。

### Don't:

- **Don't** 将无 GPS 的业务点位描绘为车辆实时位置，将业务关联线称为道路导航路线。
- **Don't** 将样本估算、演示参数或报价试算呈现为整批实测、真实成交或实际到账。
- **Don't** 把所有业务文字统一扩大到（14–16px），或把所有信息包进同尺寸指标卡。
- **Don't** 在手机上横向缩放整张桌面大屏来代替布局重排。
- **Don't** 删除或隐藏所用开源素材的来源与许可证。
