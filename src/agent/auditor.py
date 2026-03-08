"""审计师 Agent - 负责一致性检查

六大检查维度：
1. 时间一致性 - 时间线是否合理
2. 空间一致性 - 地点是否连贯
3. 角色一致性 - 行为是否符合人设
4. 情节一致性 - 前后是否矛盾
5. 世界观一致性 - 是否违反设定
6. 信息一致性 - 信息来源是否合理
"""

from .base import AgentContext, AgentResult, BaseAgent
from .context_builder import build_quick_reference
from .prompt_loader import prompt_library


class Auditor(BaseAgent):
    """审计师 Agent"""

    name = "Auditor"
    description = "逻辑审计师，专注于一性检查和质量控制，确保故事前后不矛盾"
    _system_prompt: str
    _metadata: dict

    # 最大修正尝试次数
    MAX_FIX_ATTEMPTS = 2

    def __init__(self, llm=None):
        """初始化审计师"""
        super().__init__(llm=llm)
        self._load_prompts()

    def _load_prompts(self):
        """加载提示词模板"""
        self._system_prompt = prompt_library.get_system_prompt("auditor")
        self._metadata = prompt_library.get_metadata("auditor")
        self.name = self._metadata.get("name", "Auditor")
        self.description = self._metadata.get("description", "")

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        执行审计任务

        Args:
            context: 执行上下文，需要包含:
                - user_input: 待审计的内容
                - extra.get("audit_type"): 审计类型
                  (full/quick/time/space/character/plot/world/info)
                - extra.get("previous_chapters"): 前文内容（用于信息一致性检查）
                - extra.get("attempt_count"): 当前修正尝试次数

        Returns:
            审计结果，包含:
                - issues: 问题列表
                - suggestions: 修正建议
                - fixed_content: 自动修正后的内容（如有轻微问题）
                - needs_rewrite: 是否需要打回重写
        """
        self._context = context

        content = context.user_input
        if not content:
            return AgentResult(
                success=False,
                error="缺少待审计的内容",
            )

        audit_type = context.extra.get("audit_type", "full")
        attempt_count = context.extra.get("attempt_count", 0)

        try:
            if audit_type == "full":
                issues = await self._full_audit(context, content)
            elif audit_type == "quick":
                issues = await self._quick_audit(context, content)
            else:
                issues = await self._single_dimension_audit(
                    context, content, audit_type
                )

            # 分类问题
            severe_issues = [i for i in issues if i.get("severity") == "severe"]
            medium_issues = [i for i in issues if i.get("severity") == "medium"]
            minor_issues = [i for i in issues if i.get("severity") == "minor"]

            # 判断是否需要打回重写
            needs_rewrite = False
            fixed_content = None

            if severe_issues:
                # 有严重问题，需要打回重写
                needs_rewrite = True
            elif minor_issues and not medium_issues:
                # 只有轻微问题，尝试自动修正
                fixed_content = await self._auto_fix(content, minor_issues)

            suggestions = self._generate_suggestions(issues)

            return AgentResult(
                success=len(severe_issues) == 0,
                content=self._format_report(issues, suggestions),
                issues=issues,
                suggestions=suggestions,
                extra={
                    "fixed_content": fixed_content,
                    "needs_rewrite": needs_rewrite,
                    "attempt_count": attempt_count,
                },
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"审计过程出错: {e!s}",
            )

    async def _full_audit(self, context: AgentContext, content: str) -> list[dict]:
        """全面审计"""
        issues = []

        # 六大维度
        dimensions = ["time", "space", "character", "plot", "world", "info"]

        for dimension in dimensions:
            dim_issues = await self._single_dimension_audit(context, content, dimension)
            issues.extend(dim_issues)

        return issues

    async def _quick_audit(self, context: AgentContext, content: str) -> list[dict]:
        """快速审计"""
        ctx_text = build_quick_reference(context)

        prompt = f"""你是小说逻辑审计师。请快速检查以下内容是否存在严重问题。

【已知设定】
{ctx_text}

【待检查内容】
{content}

【快速检查要点】
1. 时间是否合理？（白天/黑夜、时间顺序）
2. 地点是否连贯？（角色是否瞬移）
3. 角色行为是否合理？（符合人设吗）
4. 是否有明显矛盾？

【输出格式】
如果没有严重问题，输出：
✓ 通过快速检查

如果有问题，输出：
✗ 发现问题
├── 🔴 [严重] 问题描述
├── 🟡 [中等] 问题描述
└── 🟢 [轻微] 问题描述

只报告问题，忽略轻微瑕疵。"""

        result = await self._call_llm(prompt, system=self._system_prompt)

        return self._parse_issues(result, "general")

    async def _single_dimension_audit(
        self, context: AgentContext, content: str, dimension: str
    ) -> list[dict]:
        """单维度审计"""
        ctx_text = build_quick_reference(context)

        dimension_checks = {
            "time": """
- 时间顺序是否合理？
- 白天/黑夜是否连贯？
- 时间流逝是否有交代？
- 季节时间是否一致？""",
            "space": """
- 角色位置是否正确？
- 地点转换是否有交代？
- 是否出现瞬移？
- 地理关系是否正确？""",
            "character": """
- 行为是否符合性格？
- 能力使用是否合理？
- 语言风格是否一致？
- 关系表现是否正确？""",
            "plot": """
- 是否与前文矛盾？
- 因果关系是否合理？
- 伏笔是否需要铺垫？
- 情节推进是否得当？""",
            "world": """
- 是否违反力量规则？
- 是否违反社会制度？
- 是否违反地理设定？
- 是否违反历史背景？""",
            "info": """
- 角色知道的信息是否有来源？
- 角色是否知道不该知道的事？
- 身份/名字是否有合理揭示？
- 是否存在上帝视角泄露？""",
        }

        check_list = dimension_checks.get(dimension, "")

        # 信息一致性需要额外的前文上下文
        extra_context = ""
        if dimension == "info":
            previous_chapters = context.extra.get("previous_chapters", {})
            if previous_chapters:
                # 提取前文中的信息揭示
                info_reveals = self._extract_info_reveals(previous_chapters)
                extra_context = f"\n【前文中已揭示的信息】\n{info_reveals}"

        prompt = f"""请对以下内容进行【{dimension}】一致性审计。

【已知上下文】
{ctx_text}{extra_context}

【待审计内容】
{content}

【检查要点】
{check_list}

【输出格式】
如果没有问题：
✓ {dimension} 一致性通过

如果有问题：
⚠️ {dimension} 问题发现
├── 🔴 [严重] 第X段: 问题描述
├── 🟡 [中等] 第X段: 问题描述
└── 🟢 [轻微] 第X段: 问题描述

按严重程度标注，定位到具体段落。"""

        result = await self._call_llm(prompt, system=self._system_prompt)

        return self._parse_issues(result, dimension)

    def _extract_info_reveals(self, previous_chapters: dict) -> str:
        """
        从前文中提取已揭示的信息

        Args:
            previous_chapters: 前文章节 {章节号: 内容}

        Returns:
            信息揭示摘要
        """
        reveals = []
        for ch_num, content in sorted(previous_chapters.items()):
            # 简单提取：角色名出现、身份揭示等
            lines = []
            if "我叫" in content or "名字是" in content:
                lines.append(f"第{ch_num}章: 有角色自我介绍")
            if "原来" in content or "其实是" in content:
                lines.append(f"第{ch_num}章: 有身份揭示")
            if lines:
                reveals.extend(lines)

        return "\n".join(reveals) if reveals else "无特殊信息揭示"

    def _parse_issues(self, result: str, dimension: str) -> list[dict]:
        """解析问题"""
        issues: list[dict] = []

        if "✓" in result and "通过" in result:
            return issues

        lines = result.split("\n")
        for line in lines:
            if "├──" in line or "└──" in line:
                severity = "medium"
                if "🔴" in line or "严重" in line:
                    severity = "severe"
                elif "🟢" in line or "轻微" in line:
                    severity = "minor"

                description = line
                for marker in [
                    "├──",
                    "└──",
                    "🔴",
                    "🟡",
                    "🟢",
                    "[严重]",
                    "[中等]",
                    "[轻微]",
                ]:
                    description = description.replace(marker, "")

                issues.append(
                    {
                        "dimension": dimension,
                        "severity": severity,
                        "description": description.strip(),
                    }
                )

        return issues

    def _generate_suggestions(self, issues: list[dict]) -> list[str]:
        """生成修正建议"""
        suggestions = []

        dimension_fixes = {
            "time": "检查时间线设定",
            "space": "添加地点转换描写",
            "character": "回顾角色人设",
            "plot": "添加铺垫或调整情节",
            "world": "检查设定规则",
            "info": "补充信息来源或添加揭示场景",
        }

        for issue in issues:
            dimension = issue.get("dimension", "")
            desc = issue.get("description", "")
            fix = dimension_fixes.get(dimension, "检查相关设定")
            suggestions.append(f"[{dimension}] {desc} → 建议：{fix}")

        return suggestions

    async def _auto_fix(self, content: str, minor_issues: list[dict]) -> str:
        """
        自动修正轻微问题

        Args:
            content: 原始内容
            minor_issues: 轻微问题列表

        Returns:
            修正后的内容
        """
        if not minor_issues:
            return content

        issues_text = "\n".join(
            f"- [{i.get('dimension')}] {i.get('description')}"
            for i in minor_issues
        )

        prompt = f"""请修正以下内容中的轻微问题。

【原始内容】
{content}

【需要修正的问题】
{issues_text}

【修正要求】
1. 只修正上述问题，不要大幅改写
2. 保持原有的叙事风格和节奏
3. 修正后直接输出完整内容，不要解释

【输出格式】
直接输出修正后的完整章节内容。"""

        fixed = await self._call_llm(prompt, system=self._system_prompt)
        return fixed

    def _format_report(self, issues: list[dict], suggestions: list[str]) -> str:
        """格式化报告"""
        if not issues:
            return "✓ 审计通过，未发现问题"

        lines = ["═══════════════════════════════════════"]
        lines.append("           审计报告")
        lines.append("═══════════════════════════════════════")
        lines.append("")

        severe = [i for i in issues if i.get("severity") == "severe"]
        medium = [i for i in issues if i.get("severity") == "medium"]
        minor = [i for i in issues if i.get("severity") == "minor"]

        lines.append("【问题汇总】")
        lines.append("│")

        if severe:
            lines.append("├── 🔴 严重问题（必须修正）")
            for i in severe:
                lines.append(f"│   └── [{i.get('dimension')}] {i.get('description')}")

        if medium:
            lines.append("├── 🟡 中等问题（建议修正）")
            for i in medium:
                lines.append(f"│   └── [{i.get('dimension')}] {i.get('description')}")

        if minor:
            lines.append("└── 🟢 轻微问题（可选修正）")
            for i in minor:
                lines.append(f"    └── [{i.get('dimension')}] {i.get('description')}")

        if suggestions:
            lines.append("")
            lines.append("【修正建议】")
            for s in suggestions:
                lines.append(f"→ {s}")

        lines.append("")
        lines.append("═══════════════════════════════════════")

        return "\n".join(lines)

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self._system_prompt


async def quick_check(context: AgentContext, content: str) -> list[dict]:
    """快速检查便捷方法"""
    auditor = Auditor()
    if context.llm:
        auditor.set_llm(context.llm)

    result = await auditor.execute(
        AgentContext(
            graph=context.graph,
            timeline=context.timeline,
            world_map=context.world_map,
            characters=context.characters,
            user_input=content,
            extra={"audit_type": "quick"},
            llm=context.llm,
            knowledge=context.knowledge,
        )
    )

    return result.issues
