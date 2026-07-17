"""Fast, deterministic and conservative goal-to-tool recommendations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .contracts import SessionConfig, TargetRule
from .goal_scenarios import GoalScenarioStore


PROCESS = "process"
TITLE = "window_title"


@dataclass(frozen=True)
class ScenarioSuggestion:
    """A user-facing scene grouping for a small set of monitorable targets."""

    name: str
    description: str
    targets: tuple[TargetRule, ...]


def _process(value: str) -> TargetRule:
    return TargetRule(PROCESS, value, "exact")


def _title(value: str) -> TargetRule:
    return TargetRule(TITLE, value, "contains")


EXPLICIT_RULES: tuple[tuple[tuple[str, ...], TargetRule], ...] = (
    (("vs code", "vscode"), _process("Code.exe")),
    (("visual studio",), _process("devenv.exe")),
    (("word",), _process("WINWORD.EXE")),
    (("wps",), _process("wps.exe")),
    (("powerpoint",), _process("POWERPNT.EXE")),
    (("excel",), _process("EXCEL.EXE")),
    (("matlab",), _title("MATLAB")),
    (("学习通",), _title("学习通")),
    (("雨课堂",), _title("雨课堂")),
    (("知网",), _title("知网")),
    (("语雀",), _title("语雀")),
    (("notion",), _title("Notion")),
    (("飞书",), _title("飞书")),
)

CODING_WORDS = ("代码", "编程", "python", "java", "前端", "后端", "算法", "debug", "调试", "项目开发")
WRITING_WORDS = ("论文", "报告", "周报", "写作", "文案", "简历", "策划案", "方案")
PRESENTATION_WORDS = ("ppt", "演示文稿", "幻灯片", "路演", "汇报ppt")
SHEET_WORDS = ("excel", "表格", "数据分析", "统计", "报表", "数据清洗")
STUDY_WORDS = ("复习", "备考", "刷题", "学习", "背单词", "考试", "作业", "习题")
READING_WORDS = ("阅读", "看书", "读完", "资料", "pdf", "文献")

SUBJECT_WORDS = (
    "高数", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理",
    "计算机", "会计", "法律", "经济学", "线性代数", "概率论",
)

COURSE_PLATFORM_WORDS = ("学习通", "雨课堂", "慕课", "mooc", "智慧树", "知到", "canvas")

BLACKLIST_TITLES = {
    "b站": "哔哩哔哩",
    "bilibili": "哔哩哔哩",
    "哔哩哔哩": "哔哩哔哩",
    "微博": "微博",
    "抖音": "抖音",
    "小红书": "小红书",
    "知乎": "知乎",
    "淘宝": "淘宝",
    "京东": "京东",
    "游戏": "游戏",
}
BLACKLIST_MARKERS = ("禁止", "不要", "不能", "别刷", "别看", "别打开", "避开")


SCENE_META = {
    "create": ("主任务", "真正产出结果的工具"),
    "course": ("课程与练习", "只按科目或明确写出的课程平台匹配"),
    "verify": ("运行与验证", "测试、计算或核对结果"),
    "reference": ("资料参考", "阅读文档和可信资料"),
    "collab": ("协作与素材", "仅保留明确需要的协作工具"),
    "extra": ("目标相关页面", "按目标关键词匹配，不放行整个浏览器"),
}

SCENE_ORDER = ("create", "course", "verify", "reference", "collab", "extra")

SCENE_BY_VALUE = {
    "code.exe": "create",
    "winword.exe": "create",
    "wps.exe": "create",
    "powerpnt.exe": "create",
    "wpp.exe": "create",
    "photoshop.exe": "create",
    "devenv.exe": "create",
    "adobe premiere pro.exe": "create",
    "jianyingpro.exe": "create",
    "学习通": "course",
    "雨课堂": "course",
    "慕课": "course",
    "mooc": "course",
    "智慧树": "course",
    "知到": "course",
    "canvas": "course",
    "作业": "course",
    "windowsterminal.exe": "verify",
    "excel.exe": "verify",
    "et.exe": "verify",
    "matlab": "verify",
    "calculatorapp.exe": "verify",
    "acrord32.exe": "reference",
    "pdf": "reference",
    "知网": "reference",
    "官方文档": "reference",
    "学习资料": "reference",
    "语雀": "collab",
    "notion": "collab",
    "obsidian.exe": "collab",
    "onenote.exe": "collab",
    "outlook.exe": "collab",
    "wemeetapp.exe": "collab",
    "zoom.exe": "collab",
    "ms-teams.exe": "collab",
    "explorer.exe": "collab",
    "飞书": "collab",
    "figma": "collab",
    "canva": "collab",
}


def _deduplicate(items: list[TargetRule]) -> tuple[TargetRule, ...]:
    seen: set[tuple[str, str, str]] = set()
    result: list[TargetRule] = []
    for item in items:
        key = (item.kind, item.value.casefold(), item.match)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return tuple(result)


def recommend_targets(
    goal: str,
    scenario_store: GoalScenarioStore | None = None,
) -> tuple[TargetRule, ...]:
    """Recommend the minimum strongly implied tool set.

    Explicitly named tools always win. Generic tasks only receive tools strongly
    implied by the task type. In particular, course platforms and collaboration
    tools are never invented when the user did not name them.
    """
    lowered = goal.casefold()
    candidates: list[TargetRule] = []
    store = scenario_store or GoalScenarioStore()

    # A user's previously confirmed setup is the strongest signal. It is kept
    # entirely on this computer and reused only for very similar goals.
    candidates.extend(store.learned_targets(goal))

    for keywords, rule in EXPLICIT_RULES:
        if any(keyword in lowered for keyword in keywords):
            candidates.append(rule)

    matched_scenarios = store.match(goal)
    for scenario in matched_scenarios:
        candidates.extend(scenario.targets)

    if any(word in lowered for word in CODING_WORDS):
        if not matched_scenarios:
            candidates.extend(
                (
                    _process("Code.exe"),
                    _process("WindowsTerminal.exe"),
                    _process("explorer.exe"),
                )
            )
        if any(word in lowered for word in ("文档", "api", "框架", "库", "查资料")):
            candidates.append(_title("官方文档"))

    # Presentation wins over the ambiguous word “汇报”. A PPT goal must not
    # simultaneously expand into Word, WPS, Canva and a research stack.
    is_presentation = any(word in lowered for word in PRESENTATION_WORDS)
    if is_presentation and not matched_scenarios:
        candidates.extend((_process("POWERPNT.EXE"), _process("wpp.exe")))
    elif any(word in lowered for word in WRITING_WORDS) and not matched_scenarios:
        candidates.extend((_process("WINWORD.EXE"), _process("wps.exe")))

    if any(word in lowered for word in SHEET_WORDS) and not matched_scenarios:
        candidates.extend((_process("EXCEL.EXE"), _process("et.exe")))

    if "matlab" in lowered:
        candidates.append(_title("MATLAB"))

    if any(word in lowered for word in ("ui", "ux", "原型", "figma")):
        candidates.append(_title("Figma"))
    elif any(word in lowered for word in ("修图", "photoshop")):
        candidates.append(_process("Photoshop.exe"))
    elif any(word in lowered for word in ("海报", "封面", "视觉设计")):
        candidates.extend((_process("Photoshop.exe"), _title("Canva")))

    is_study = any(word in lowered for word in STUDY_WORDS) or any(
        word in lowered for word in SUBJECT_WORDS
    )
    if is_study:
        subject = next((word for word in SUBJECT_WORDS if word in lowered), "")
        if subject:
            study_title = subject
        elif "作业" in lowered:
            study_title = "作业"
        else:
            study_title = "学习资料"
        # A title keyword is safer than granting the whole browser and more
        # honest than inventing Learning通 or Rain Classroom.
        # Keep the subject-specific browser/page rule even when the generic
        # study scene has already supplied PDF/calculator tools.
        candidates.append(_title(study_title))
        if not matched_scenarios:
            candidates.append(_process("AcroRd32.exe"))

    if any(word in lowered for word in READING_WORDS):
        candidates.append(_process("AcroRd32.exe"))
        if "知网" in lowered:
            candidates.append(_title("知网"))

    for platform in COURSE_PLATFORM_WORDS:
        if platform in lowered:
            candidates.append(_title("MOOC" if platform == "mooc" else platform))

    if not candidates:
        topic = re.sub(r"[，。！？,.!?\s]+", "", goal)
        topic = re.sub(r"^(我要|我想|今天|接下来|完成|做完|搞定|处理)", "", topic)
        topic = re.sub(r"^\d+(?:\.\d+)?(?:分钟|小时)", "", topic)[:12]
        candidates.append(_title(topic or "工作资料"))

    return _deduplicate(candidates)[:10]


def group_targets_by_scene(
    goal: str, targets: tuple[TargetRule, ...] | list[TargetRule]
) -> tuple[ScenarioSuggestion, ...]:
    """Turn flat monitor rules into compact, explainable work scenes."""
    del goal
    grouped: dict[str, list[TargetRule]] = {key: [] for key in SCENE_ORDER}
    for target in _deduplicate(list(targets)):
        value = target.value.casefold()
        scene = SCENE_BY_VALUE.get(value)
        if scene is None and any(subject in value for subject in SUBJECT_WORDS):
            scene = "course"
        grouped[scene or "extra"].append(target)
    result: list[ScenarioSuggestion] = []
    for key in SCENE_ORDER:
        if grouped[key]:
            name, description = SCENE_META[key]
            result.append(ScenarioSuggestion(name, description, tuple(grouped[key])))
    return tuple(result)


def infer_duration_minutes(text: str, default: int = 45) -> int:
    hour = re.search(r"(\d+(?:\.\d+)?)\s*(?:小时|h\b)", text, re.I)
    if hour:
        return max(1, min(480, round(float(hour.group(1)) * 60)))
    minute = re.search(r"(\d+)\s*(?:分钟|min\b)", text, re.I)
    if minute:
        return max(1, min(480, int(minute.group(1))))
    return default


def recommend_blocked_targets(goal: str) -> tuple[TargetRule, ...]:
    compact = goal.replace(" ", "").casefold()
    if not any(marker in compact for marker in BLACKLIST_MARKERS):
        return ()
    return _deduplicate(
        [
            _title(title)
            for keyword, title in BLACKLIST_TITLES.items()
            if keyword in compact
        ]
    )


def fallback_config_for_goal(
    goal: str,
    scenario_store: GoalScenarioStore | None = None,
) -> SessionConfig:
    compact = goal.replace(" ", "")
    blackout = any(term in compact for term in ("完全不碰电脑", "不看屏幕", "离开电脑"))
    blocked = () if blackout else recommend_blocked_targets(goal)
    targets = () if blackout or blocked else recommend_targets(goal, scenario_store)
    return SessionConfig(
        schema_version=1,
        duration_minutes=infer_duration_minutes(goal),
        mode="blackout" if blackout else ("blacklist" if blocked else "whitelist"),
        allowed_targets=targets,
        blocked_targets=blocked,
        grace_seconds=8,
        check_interval_seconds=2,
        popup_cooldown_seconds=30,
        max_alerts=10,
        roast_intensity=(
            "spicy" if any(term in compact for term in ("狠一点", "毒舌", "不要惯着")) else "mild"
        ),
        needs_clarification=False,
        clarification_question="",
    )


def friendly_target_label(rule: TargetRule) -> str:
    process_names = {
        "code.exe": "VS Code",
        "windowsterminal.exe": "终端",
        "winword.exe": "Word",
        "wps.exe": "WPS文字",
        "powerpnt.exe": "PowerPoint",
        "wpp.exe": "WPS演示",
        "excel.exe": "Excel",
        "et.exe": "WPS表格",
        "acrord32.exe": "PDF阅读器",
        "photoshop.exe": "Photoshop",
    }
    if rule.kind == "process":
        return process_names.get(rule.value.casefold(), rule.value.removesuffix(".exe"))
    return rule.value
