"""审计师 Agent - 负责一致性检查

五大检查维度：
1. 时间一致性 - 时间线是否合理
2. 空间一致性 - 地点是否连贯
3. 角色一致性 - 行为是否符合人设
4. 情节一致性 - 前后是否矛盾
5. 世界观一致性 - 是否违反设定
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
                  (full/quick/time/space/character/plot/world)

        Returns:
            审计结果
        """
        self._context = context

        content = context.user_input
        if not content:
            return AgentResult(
                success=False,
                error="缺少待审计的内容",
            )

        audit_type = context.extra.get("audit_type", "full")

        try:
            if audit_type == "full":
                issues = await self._full_audit(context, content)
            elif audit_type == "quick":
                issues = await self._quick_audit(context, content)
            else:
                issues = await self._single_dimension_audit(
                    context, content, audit_type
                )

            suggestions = self._generate_suggestions(issues)

            return AgentResult(
                success=len(issues) == 0
                or all(i.get("severity") != "severe" for i in issues),
                content=self._format_report(issues, suggestions),
                issues=issues,
                suggestions=suggestions,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"审计过程出错: {e!s}",
            )

    async def _full_audit(self, context: AgentContext, content: str) -> list[dict]:
        """全面审计"""
        issues = []

        dimensions = ["time", "space", "character", "plot", "world"]

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
        }

        check_list = dimension_checks.get(dimension, "")

        prompt = f"""请对以下内容进行【{dimension}】一致性审计。

【已知上下文】
{ctx_text}

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
        }

        for issue in issues:
            dimension = issue.get("dimension", "")
            desc = issue.get("description", "")
            fix = dimension_fixes.get(dimension, "检查相关设定")
            suggestions.append(f"[{dimension}] {desc} → 建议：{fix}")

        return suggestions

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
