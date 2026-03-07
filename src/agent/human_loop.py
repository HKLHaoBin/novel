"""
人在回路交互模块

提供设计确认、内容编辑、选项选择等交互功能。
支持命令行输入和编辑器两种修改方式。
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from typing import Any


class EditMode(Enum):
    """编辑模式"""

    CLI = "cli"  # 命令行输入
    EDITOR = "editor"  # 编辑器
    AUTO = "auto"  # 自动选择


@dataclass
class InteractionResult:
    """交互结果"""

    confirmed: bool
    modified: bool
    content: str
    feedback: str = ""
    extra: dict[str, Any] | None = None


class HumanLoopManager:
    """人在回路管理器"""

    def __init__(
        self,
        edit_mode: EditMode = EditMode.AUTO,
        auto_confirm: bool = False,
        editor: str | None = None,
    ):
        """
        初始化交互管理器

        Args:
            edit_mode: 编辑模式（cli/editor/auto）
            auto_confirm: 自动确认（跳过交互）
            editor: 指定编辑器（默认使用 $EDITOR 或 vi）
        """
        self.edit_mode = edit_mode
        self.auto_confirm = auto_confirm
        self.editor = editor or os.environ.get("EDITOR", "vi")

    def _print_separator(self, char: str = "=", length: int = 60) -> None:
        """打印分隔线"""
        print(char * length)

    def _print_header(self, title: str) -> None:
        """打印标题头"""
        self._print_separator()
        print(f" {title}")
        self._print_separator()

    def confirm(
        self,
        content: str,
        title: str = "确认内容",
        allow_edit: bool = True,
    ) -> InteractionResult:
        """
        确认内容

        Args:
            content: 待确认的内容
            title: 标题
            allow_edit: 是否允许编辑

        Returns:
            InteractionResult
        """
        if self.auto_confirm:
            return InteractionResult(
                confirmed=True, modified=False, content=content
            )

        self._print_header(title)
        print(content)
        self._print_separator()

        while True:
            if allow_edit:
                prompt = "选项: [确认(Y)/编辑(E)/取消(N)]: "
            else:
                prompt = "选项: [确认(Y)/取消(N)]: "

            user_input = input(prompt).strip().lower()

            if user_input in ["y", "yes", "确认"]:
                return InteractionResult(
                    confirmed=True, modified=False, content=content
                )
            if user_input in ["n", "no", "取消"]:
                return InteractionResult(
                    confirmed=False, modified=False, content=content
                )
            if allow_edit and user_input in ["e", "edit", "编辑"]:
                edited = self._edit_content(content, title)
                return InteractionResult(
                    confirmed=True,
                    modified=True,
                    content=edited,
                    feedback="用户已编辑",
                )

            print("无效选项，请重新输入")

    def edit(
        self,
        content: str,
        title: str = "编辑内容",
        mode: EditMode | None = None,
    ) -> InteractionResult:
        """
        编辑内容

        Args:
            content: 待编辑的内容
            title: 标题
            mode: 编辑模式（覆盖默认设置）

        Returns:
            InteractionResult
        """
        if self.auto_confirm:
            return InteractionResult(
                confirmed=True, modified=False, content=content
            )

        edit_mode = mode or self.edit_mode

        if edit_mode == EditMode.AUTO:
            # 自动选择：内容短用 CLI，长用编辑器
            edit_mode = (
                EditMode.CLI if len(content.split("\n")) <= 5 else EditMode.EDITOR
            )

        edited = self._edit_content(content, title, edit_mode)
        return InteractionResult(
            confirmed=True,
            modified=(edited != content),
            content=edited,
        )

    def _edit_content(
        self,
        content: str,
        title: str,
        mode: EditMode = EditMode.AUTO,
    ) -> str:
        """
        内部编辑方法

        Args:
            content: 待编辑内容
            title: 标题
            mode: 编辑模式

        Returns:
            编辑后的内容
        """
        if mode == EditMode.AUTO:
            mode = (
                EditMode.CLI if len(content.split("\n")) <= 5 else EditMode.EDITOR
            )

        if mode == EditMode.CLI:
            return self._edit_cli(content, title)
        return self._edit_editor(content, title)

    def _edit_cli(self, content: str, title: str) -> str:
        """命令行编辑"""
        print(f"\n【{title}】")
        print("当前内容（直接回车保持原样，输入新内容替换）:")
        print("-" * 40)
        print(content)
        print("-" * 40)

        lines = content.split("\n")
        new_lines = []

        for i, line in enumerate(lines):
            new_line = input(f"行{i + 1}> ").strip()
            if new_line:
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        return "\n".join(new_lines)

    def _edit_editor(self, content: str, title: str) -> str:
        """编辑器编辑"""
        # 创建临时文件
        suffix = ".md"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8"
        ) as f:
            f.write(f"# {title}\n\n")
            f.write(content)
            f.write("\n\n# 编辑完成后保存退出\n")
            temp_path = f.name

        try:
            # 打开编辑器
            subprocess.run([self.editor, temp_path], check=True)

            # 读取编辑后的内容
            with open(temp_path, encoding="utf-8") as f:
                edited = f.read()

            # 移除添加的注释
            lines = edited.split("\n")
            # 移除标题和结尾注释
            content_lines = []
            in_content = False
            for line in lines:
                if line.startswith("# ") and not in_content:
                    continue
                if line.startswith("# 编辑完成后保存退出"):
                    break
                in_content = True
                content_lines.append(line)

            return "\n".join(content_lines).strip()
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def choose(
        self,
        options: list[dict[str, str]],
        prompt: str = "请选择",
        default: int = 0,
    ) -> InteractionResult:
        """
        单选

        Args:
            options: 选项列表 [{"label": "...", "description": "..."}, ...]
            prompt: 提示信息
            default: 默认选项索引

        Returns:
            InteractionResult
        """
        if self.auto_confirm:
            return InteractionResult(
                confirmed=True,
                modified=False,
                content=options[default]["label"] if options else "",
                extra={"index": default},
            )

        print(f"\n{prompt}:")
        for i, opt in enumerate(options):
            default_marker = " [默认]" if i == default else ""
            print(f"  {i + 1}. {opt['label']}{default_marker}")
            if "description" in opt:
                print(f"     {opt['description']}")

        while True:
            user_input = input(f"选择 (1-{len(options)}): ").strip()

            if not user_input:
                # 使用默认值
                return InteractionResult(
                    confirmed=True,
                    modified=False,
                    content=options[default]["label"],
                    extra={"index": default},
                )

            if user_input.isdigit():
                idx = int(user_input) - 1
                if 0 <= idx < len(options):
                    return InteractionResult(
                        confirmed=True,
                        modified=(idx != default),
                        content=options[idx]["label"],
                        extra={"index": idx},
                    )

            print("无效选项，请重新输入")

    def multi_select(
        self,
        options: list[dict[str, str]],
        prompt: str = "请选择（多选）",
        defaults: list[int] | None = None,
    ) -> InteractionResult:
        """
        多选

        Args:
            options: 选项列表
            prompt: 提示信息
            defaults: 默认选项索引列表

        Returns:
            InteractionResult
        """
        defaults = defaults or []

        if self.auto_confirm:
            selected_labels = [
                options[i]["label"] for i in defaults if i < len(options)
            ]
            return InteractionResult(
                confirmed=True,
                modified=False,
                content=",".join(selected_labels),
                extra={"indices": defaults},
            )

        print(f"\n{prompt}:")
        for i, opt in enumerate(options):
            checked = "[x]" if i in defaults else "[ ]"
            print(f"  {i + 1}. {checked} {opt['label']}")
            if "description" in opt:
                print(f"      {opt['description']}")

        print("输入数字切换选择，空行确认")

        selected_indices: set[int] = set(defaults)
        while True:
            user_input = input("选择: ").strip()

            if not user_input:
                # 确认选择
                selected_labels = [
                    options[i]["label"] for i in sorted(selected_indices)
                ]
                return InteractionResult(
                    confirmed=True,
                    modified=(set(defaults) != selected_indices),
                    content=",".join(selected_labels),
                    extra={"indices": sorted(selected_indices)},
                )

            # 切换选择
            for part in user_input.split():
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(options):
                        if idx in selected_indices:
                            selected_indices.discard(idx)
                        else:
                            selected_indices.add(idx)

    def input_text(
        self,
        prompt: str = "请输入",
        default: str = "",
        multiline: bool = False,
    ) -> InteractionResult:
        """
        文本输入

        Args:
            prompt: 提示信息
            default: 默认值
            multiline: 是否多行输入

        Returns:
            InteractionResult
        """
        if self.auto_confirm:
            return InteractionResult(
                confirmed=True, modified=False, content=default
            )

        if multiline:
            print(f"{prompt}（输入空行结束）:")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
            content = "\n".join(lines)
        else:
            default_hint = f" [{default}]" if default else ""
            content = input(f"{prompt}{default_hint}: ").strip()
            if not content and default:
                content = default

        return InteractionResult(
            confirmed=True,
            modified=(content != default),
            content=content,
        )

    def design_phase_confirm(
        self,
        phase_name: str,
        content: str,
        phase_num: int = 0,
        total_phases: int = 0,
    ) -> InteractionResult:
        """
        设计阶段确认

        Args:
            phase_name: 阶段名称（核心种子/角色/世界观/情节/蓝图）
            content: 阶段内容
            phase_num: 当前阶段号
            total_phases: 总阶段数

        Returns:
            InteractionResult
        """
        if self.auto_confirm:
            return InteractionResult(
                confirmed=True, modified=False, content=content
            )

        title = f"设计阶段 [{phase_num}/{total_phases}]: {phase_name}"
        return self.confirm(content, title, allow_edit=True)

    def chapter_preview(
        self,
        chapter_num: int,
        title: str,
        content: str,
    ) -> InteractionResult:
        """
        章节预览

        Args:
            chapter_num: 章节号
            title: 章节标题
            content: 章节内容

        Returns:
            InteractionResult
        """
        if self.auto_confirm:
            return InteractionResult(
                confirmed=True, modified=False, content=content
            )

        header = f"第 {chapter_num} 章「{title}」"
        self._print_header(header)

        # 显示内容（长内容截断预览）
        lines = content.split("\n")
        if len(lines) > 30:
            preview = "\n".join(lines[:30])
            print(preview)
            print(f"\n... 省略 {len(lines) - 30} 行 ...")
            print(f"\n总字数: {len(content)}")
        else:
            print(content)

        self._print_separator()

        while True:
            prompt = "选项: [确认(Y)/编辑(E)/重写(R)/放弃(X)]: "
            user_input = input(prompt).strip().lower()

            if user_input in ["y", "yes", "确认"]:
                return InteractionResult(
                    confirmed=True, modified=False, content=content
                )
            if user_input in ["x", "exit", "放弃"]:
                return InteractionResult(
                    confirmed=False, modified=False, content=content
                )
            if user_input in ["e", "edit", "编辑"]:
                edited = self._edit_content(content, header)
                return InteractionResult(
                    confirmed=True,
                    modified=True,
                    content=edited,
                )
            if user_input in ["r", "rewrite", "重写"]:
                feedback = input("请输入重写要求: ").strip()
                return InteractionResult(
                    confirmed=False,
                    modified=False,
                    content=content,
                    feedback=feedback,
                )

            print("无效选项，请重新输入")

    def audit_feedback(
        self,
        issues: list[dict[str, Any]],
        content: str,
    ) -> InteractionResult:
        """
        审计反馈

        Args:
            issues: 问题列表 [{"type": "...", "message": "...", "severity": "..."}]
            content: 原始内容

        Returns:
            InteractionResult
        """
        if self.auto_confirm:
            return InteractionResult(
                confirmed=True, modified=False, content=content
            )

        if not issues:
            print("审计通过，未发现问题")
            return InteractionResult(
                confirmed=True, modified=False, content=content
            )

        self._print_header("审计报告")
        print(f"发现 {len(issues)} 个问题:\n")

        for i, issue in enumerate(issues):
            severity = issue.get("severity", "info")
            msg = issue.get("message", str(issue))
            icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(
                severity, "•"
            )
            print(f"{i + 1}. {icon} [{severity}] {msg}")

        self._print_separator()

        # 让用户选择如何处理
        options = [
            {"label": "自动修复", "description": "让 LLM 自动修复所有问题"},
            {"label": "手动编辑", "description": "打开编辑器手动修改"},
            {"label": "忽略问题", "description": "忽略这些问题，继续下一步"},
            {"label": "逐个处理", "description": "逐个查看问题并决定处理方式"},
        ]

        result = self.choose(options, "如何处理这些问题?")
        action = result.content

        if action == "自动修复":
            return InteractionResult(
                confirmed=False,
                modified=False,
                content=content,
                feedback="auto_fix",
            )
        if action == "手动编辑":
            edited = self._edit_content(content, "修复问题")
            return InteractionResult(
                confirmed=True, modified=True, content=edited
            )
        if action == "忽略问题":
            return InteractionResult(
                confirmed=True, modified=False, content=content
            )
        # 逐个处理
        return self._handle_issues_one_by_one(issues, content)

    def _handle_issues_one_by_one(
        self,
        issues: list[dict[str, Any]],
        content: str,
    ) -> InteractionResult:
        """逐个处理问题"""
        fixes = []
        for i, issue in enumerate(issues):
            print(f"\n问题 {i + 1}/{len(issues)}:")
            print(f"  {issue.get('message', str(issue))}")

            options = [
                {"label": "修复", "description": "修复此问题"},
                {"label": "忽略", "description": "忽略此问题"},
                {"label": "跳过剩余", "description": "跳过所有剩余问题"},
            ]

            result = self.choose(options, "处理方式")
            if result.content == "修复":
                fix = input("请输入修复内容（或留空让 LLM 自动修复）: ").strip()
                fixes.append({"issue": issue, "fix": fix})
            elif result.content == "跳过剩余":
                break

        if fixes:
            return InteractionResult(
                confirmed=False,
                modified=False,
                content=content,
                feedback="apply_fixes",
                extra={"fixes": fixes},
            )

        return InteractionResult(
            confirmed=True, modified=False, content=content
        )
