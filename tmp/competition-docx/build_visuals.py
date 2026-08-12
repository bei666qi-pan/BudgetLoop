from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "submission/budgetloop-loop-engineering/assets"
DIAGRAMS = OUT / "diagrams"
REAL = OUT / "real"
FONT_REG = "/System/Library/AssetsV2/com_apple_MobileAsset_Font8/86ba2c91f017a3749571a82f2c6d890ac7ffb2fb.asset/AssetData/PingFang.ttc"

BLUE = "#2F6BEB"
NAVY = "#0B1F3A"
MUTED = "#66758A"
PALE = "#F4F7FC"
LINE = "#DCE5F2"
GREEN = "#18A66A"
GOLD = "#E6A817"
RED = "#D95D5D"
WHITE = "#FFFFFF"


def font(size, bold=False):
    return ImageFont.truetype(FONT_REG, size=size, index=2 if bold else 3)


def centered(draw, box, text, fnt, fill=NAVY):
    x1, y1, x2, y2 = box
    b = draw.textbbox((0, 0), text, font=fnt)
    draw.text(((x1 + x2 - (b[2] - b[0])) / 2, (y1 + y2 - (b[3] - b[1])) / 2 - b[1]), text, font=fnt, fill=fill)


def rounded(draw, box, fill=WHITE, outline=LINE, radius=28, width=3):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def arrow(draw, start, end, color=BLUE, width=7):
    draw.line([start, end], fill=color, width=width)
    ex, ey = end
    sx, sy = start
    if abs(ex - sx) > abs(ey - sy):
        direction = 1 if ex > sx else -1
        pts = [(ex, ey), (ex - direction * 18, ey - 12), (ex - direction * 18, ey + 12)]
    else:
        direction = 1 if ey > sy else -1
        pts = [(ex, ey), (ex - 12, ey - direction * 18), (ex + 12, ey - direction * 18)]
    draw.polygon(pts, fill=color)


def header(draw, title, subtitle):
    draw.text((70, 45), title, font=font(46, True), fill=NAVY)
    draw.text((72, 108), subtitle, font=font(23), fill=MUTED)
    draw.rounded_rectangle((70, 148, 250, 157), radius=5, fill=BLUE)


def loop_cycle():
    im = Image.new("RGB", (1600, 900), WHITE)
    d = ImageDraw.Draw(im)
    header(d, "闭环工程", "每一轮都由真实执行结果驱动下一次决策")
    steps = [
        ("感知", "调用、工具、测试、差异"),
        ("决策", "预算、风险、优先级"),
        ("执行", "智能体与工具动作"),
        ("反馈", "退出码、验收、进展"),
        ("优化", "重试、回滚、收敛"),
    ]
    boxes = [(100, 310, 360, 500), (420, 210, 680, 400), (740, 310, 1000, 500), (1060, 210, 1320, 400), (580, 600, 840, 790)]
    for (title, sub), box in zip(steps, boxes):
        rounded(d, box, fill=PALE if title != "执行" else "#EAF1FF", outline=BLUE)
        centered(d, (box[0], box[1] + 26, box[2], box[1] + 95), title, font(34, True), BLUE)
        centered(d, (box[0] + 15, box[1] + 100, box[2] - 15, box[3] - 20), sub, font(21), MUTED)
    arrow(d, (360, 405), (420, 325))
    arrow(d, (680, 325), (740, 405))
    arrow(d, (1000, 405), (1060, 325))
    arrow(d, (1190, 400), (840, 665))
    arrow(d, (580, 690), (230, 500))
    rounded(d, (1120, 555, 1490, 780), fill="#F0FBF6", outline=GREEN)
    centered(d, (1140, 580, 1470, 645), "闭环结果", font(30, True), GREEN)
    for i, t in enumerate(["可运行", "可验证", "可追溯", "可控预算"]):
        d.text((1170, 655 + i * 30), "✓ " + t, font=font(20), fill=NAVY)
    im.save(DIAGRAMS / "loop-engineering-cycle.png")


def architecture():
    im = Image.new("RGB", (1600, 1000), WHITE)
    d = ImageDraw.Draw(im)
    header(d, "BudgetLoop 系统架构", "控制平面掌握预算、状态、审批与证据；执行引擎负责推理和动作")
    layers = [
        ("操作与可视化", "网页控制台 · 实时事件 · 团队指挥台 · 最终报告", "#EAF1FF"),
        ("控制平面", "任务状态机 · 原子预算 · 审批 · 评分 · 策略切换", "#EEF4FF"),
        ("事实与队列", "关系数据库唯一事实源 · 内存队列与心跳", "#F4F7FC"),
        ("智能体团队执行层", "角色分工 · 共享上下文 · 消息 · 任务移交 · 工具调用", "#F0FBF6"),
        ("隔离与证据", "每次运行独立工作区 · 代码工作树 · 测试 · 差异 · 工件", "#FFF8E8"),
    ]
    y = 210
    for title, sub, fill in layers:
        rounded(d, (150, y, 1450, y + 125), fill=fill, outline=LINE, radius=24)
        d.text((200, y + 25), title, font=font(30, True), fill=BLUE if title != "智能体团队执行层" else GREEN)
        d.text((500, y + 34), sub, font=font(23), fill=NAVY)
        if y < 750:
            arrow(d, (800, y + 125), (800, y + 160), color=MUTED, width=5)
        y += 160
    rounded(d, (1120, 180, 1490, 265), fill=WHITE, outline=BLUE)
    centered(d, (1130, 185, 1480, 255), "BudgetLoop", font(28, True), BLUE)
    im.save(DIAGRAMS / "system-architecture.png")


def sequence():
    im = Image.new("RGB", (1600, 1000), WHITE)
    d = ImageDraw.Draw(im)
    header(d, "智能体团队与预算控制时序", "从目标确认到可验证交付，每一步都有预算检查和证据回流")
    actors = ["用户", "控制平面", "团队统筹", "执行智能体", "验证工具"]
    xs = [150, 455, 780, 1090, 1400]
    for x, a in zip(xs, actors):
        rounded(d, (x - 105, 190, x + 105, 260), fill="#EAF1FF", outline=BLUE, radius=20)
        centered(d, (x - 100, 195, x + 100, 255), a, font(24, True), NAVY)
        d.line((x, 260, x, 920), fill=LINE, width=3)
    events = [
        (0, 1, 315, "提交目标与验收条件"),
        (1, 2, 405, "拆解阶段并分配团队预算"),
        (2, 3, 495, "发送任务与共享上下文"),
        (3, 1, 585, "调用前原子预算预留"),
        (1, 3, 665, "允许执行或切换策略"),
        (3, 4, 745, "运行代码、工具与测试"),
        (4, 1, 825, "回传退出码和验收证据"),
        (1, 0, 905, "报告结果、预算与下一步"),
    ]
    for src, dst, y, label in events:
        color = GREEN if "证据" in label or "报告" in label else BLUE
        arrow(d, (xs[src], y), (xs[dst], y), color=color, width=5)
        mid = (xs[src] + xs[dst]) / 2
        b = d.textbbox((0, 0), label, font=font(19))
        d.rectangle((mid - (b[2] - b[0]) / 2 - 8, y - 31, mid + (b[2] - b[0]) / 2 + 8, y - 5), fill=WHITE)
        d.text((mid - (b[2] - b[0]) / 2, y - 30), label, font=font(19), fill=NAVY)
    im.save(DIAGRAMS / "agent-team-budget-sequence.png")


def evidence_card(path, title, subtitle, metrics):
    im = Image.new("RGB", (1600, 900), WHITE)
    d = ImageDraw.Draw(im)
    header(d, title, subtitle)
    card_w = 330
    gap = 35
    start = 70
    for i, (label, value, note, color) in enumerate(metrics):
        x = start + i * (card_w + gap)
        rounded(d, (x, 230, x + card_w, 500), fill=PALE, outline=LINE)
        d.text((x + 28, 265), label, font=font(24, True), fill=MUTED)
        d.text((x + 28, 325), value, font=font(48, True), fill=color)
        d.text((x + 28, 410), note, font=font(20), fill=MUTED)
    rounded(d, (70, 580, 1530, 790), fill="#F0FBF6", outline=GREEN)
    d.text((110, 620), "证据说明", font=font(27, True), fill=GREEN)
    d.text((110, 680), "数据摘录自真实完成态运行记录；费用未配置价格，因此不用于成本结论。", font=font(25), fill=NAVY)
    d.text((110, 730), "原始记录保留于项目工作区，本图仅做中文化的信息重排。", font=font(22), fill=MUTED)
    im.save(path)


def localized_real_assets():
    evidence_card(
        REAL / "真实运行摘要.png",
        "BudgetLoop 真实运行摘要",
        "完成态受管运行，展示闭环轮次、调用、令牌与执行时间",
        [("运行状态", "已完成", "闭环正常收敛", GREEN), ("闭环轮次", "3 轮", "计划、执行、验证", BLUE), ("模型调用", "7 次", "上限 20 次", BLUE), ("执行时间", "1分28秒", "上限 15 分钟", GOLD)],
    )
    evidence_card(
        REAL / "真实令牌观测.png",
        "BudgetLoop 真实令牌观测",
        "逐调用统计来自运行观测页，数字按中文单位重排",
        [("总令牌", "8.68 万", "7 次模型调用", BLUE), ("输入令牌", "8.54 万", "含上下文与缓存", NAVY), ("输出令牌", "0.14 万", "模型生成内容", GREEN), ("缓存令牌", "6.91 万", "缓存命中约 45%", GOLD)],
    )

    desktop_source = REAL / "budget-tracker-desktop-real.png"
    if desktop_source.exists():
        src = Image.open(desktop_source).convert("RGB")
        crop = src.crop((350, 0, 1150, 220)).resize((1280, 352))
        canvas = Image.new("RGB", (1600, 700), WHITE)
        d = ImageDraw.Draw(canvas)
        header(d, "预算追踪器真实桌面输出", "真实生成物局部截图：标题、余额、收入与支出汇总")
        canvas.paste(crop, (160, 220))
        d.rounded_rectangle((150, 210, 1450, 585), radius=24, outline=BLUE, width=4)
        d.text((160, 620), "真实输出 · 未进行产品化重绘", font=font(23, True), fill=GREEN)
        canvas.save(REAL / "真实预算追踪器桌面.png")

    mobile_source = REAL / "budget-tracker-mobile-real.png"
    if mobile_source.exists():
        src = Image.open(mobile_source).convert("RGB")
        crop = src.crop((0, 640, 390, 844)).resize((780, 408))
        canvas = Image.new("RGB", (1600, 760), WHITE)
        d = ImageDraw.Draw(canvas)
        header(d, "预算追踪器真实移动端输出", "390 × 844 验收视口局部截图：添加记录与交易历史")
        canvas.paste(crop, (410, 230))
        d.rounded_rectangle((400, 220, 1200, 658), radius=24, outline=BLUE, width=4)
    else:
        canvas = Image.open(REAL / "真实预算追踪器移动端.png").convert("RGB")
        d = ImageDraw.Draw(canvas)
        d.rectangle((0, 670, 1600, 760), fill=WHITE)
    d.text((410, 690), "真实输出 · 浏览器自动化验证无横向溢出", font=font(23, True), fill=GREEN)
    canvas.save(REAL / "真实预算追踪器移动端.png")

    for old in [
        "budgetloop-run-command-center.png",
        "budgetloop-token-observatory.png",
        "budget-tracker-desktop-real.png",
        "budget-tracker-mobile-real.png",
    ]:
        (REAL / old).unlink(missing_ok=True)


if __name__ == "__main__":
    DIAGRAMS.mkdir(parents=True, exist_ok=True)
    REAL.mkdir(parents=True, exist_ok=True)
    loop_cycle()
    architecture()
    sequence()
    localized_real_assets()
