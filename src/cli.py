#!/usr/bin/env python3
"""小说生成器命令行工具"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

# Rich Console
console = Console()

# 默认配置路径
DEFAULT_CONFIG_PATH = Path.home() / ".novel" / "config.json"


def load_config() -> dict[str, Any]:
    """加载配置文件"""
    config_path = DEFAULT_CONFIG_PATH

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]

    return {}


def save_config(config: dict[str, Any]) -> None:
    """保存配置文件"""
    config_path = DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_llm_config() -> dict[str, Any]:
    """获取 LLM 配置（优先环境变量，其次配置文件）"""
    config = load_config()

    return {
        "type": os.environ.get("NOVEL_LLM_TYPE", config.get("llm_type", "compatible")),
        "api_key": os.environ.get("NOVEL_API_KEY", config.get("api_key", "")),
        "base_url": os.environ.get("NOVEL_BASE_URL", config.get("base_url", "")),
        "model": os.environ.get("NOVEL_MODEL", config.get("model", "deepseek-v3")),
    }


async def cmd_config(args: argparse.Namespace) -> int:
    """配置命令"""
    config = load_config()

    if args.api_key:
        config["api_key"] = args.api_key
        print(f"已设置 API Key: {args.api_key[:8]}...")

    if args.base_url:
        config["base_url"] = args.base_url
        console.print(f"[green]✓[/green] 已设置 Base URL: [cyan]{args.base_url}[/cyan]")

    if args.model:
        config["model"] = args.model
        console.print(f"[green]✓[/green] 已设置模型: [cyan]{args.model}[/cyan]")

    if args.llm_type:
        config["llm_type"] = args.llm_type
        console.print(f"[green]✓[/green] 已设置 LLM 类型: [cyan]{args.llm_type}[/cyan]")

    if config:
        save_config(config)
        console.print(f"\n[dim]配置已保存到: {DEFAULT_CONFIG_PATH}[/dim]")
    else:
        # 显示当前配置
        table = Table(title="当前配置", show_header=False)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        for key, value in config.items():
            if key == "api_key" and value:
                table.add_row(key, f"{value[:8]}...")
            else:
                table.add_row(key, str(value) if value else "[dim]未设置[/dim]")
        console.print(table)

    return 0


async def cmd_create(args: argparse.Namespace) -> int:
    """创建小说"""
    from src.generator import NovelGenerator

    llm_config = get_llm_config()

    if not llm_config.get("api_key"):
        console.print(
            "[red]错误:[/red] 未配置 API Key，"
            "请先运行 'novel config --api-key YOUR_KEY'"
        )
        return 1

    generator = NovelGenerator(
        llm_config=llm_config,
        save_dir=args.save_dir or "./novels",
        knowledge_db=args.db or "./novel_memory.db",
    )

    def on_progress(stage: str, message: str):
        if args.verbose:
            console.print(f"[dim]  {message}[/dim]")

    generator.on_progress(on_progress)

    try:
        with console.status("[bold blue]正在创建小说...[/bold blue]"):
            novel_ctx = await generator.create_novel(
                title=args.title,
                user_prompt=args.prompt,
                total_chapters=args.chapters,
                word_count_per_chapter=args.words,
            )

        console.print(
            Panel(
                f"[bold]{novel_ctx.snapshot.title}[/bold]\n\n"
                f"[dim]ID:[/dim] {novel_ctx.snapshot.id}\n"
                f"[dim]章节:[/dim] {args.chapters} 章\n"
                f"[dim]每章:[/dim] {args.words} 字",
                title="✨ 小说已创建",
                border_style="green",
            )
        )

        if args.design:
            with console.status("[bold blue]🎨 正在进行架构设计...[/bold blue]"):
                result = await generator.design()

            if result.success:
                if args.interactive:
                    console.print(
                        Panel(
                            result.content,
                            title="📋 设计结果",
                            border_style="blue",
                        )
                    )

                    while True:
                        user_input = (
                            console.input(
                                "\n[bold]选项:[/bold] [确认/修改/重做/取消] "
                            )
                            .strip()
                            .lower()
                        )

                        if user_input in ["确认", "y", "yes", "ok"]:
                            console.print("[green]✓ 设计已确认![/green]")
                            # 显示最终设计蓝图
                            console.print(
                                Panel(
                                    result.content,
                                    title="📋 最终设计蓝图",
                                    border_style="green",
                                )
                            )
                            break
                        elif user_input in ["修改", "m", "modify"]:
                            console.print(
                                "\n[dim]请输入修改建议（输入空行结束）:[/dim]"
                            )
                            lines = []
                            while True:
                                line = console.input()
                                if not line:
                                    break
                                lines.append(line)

                            if lines:
                                feedback = "\n".join(lines)
                                console.print(
                                    "\n[yellow]正在根据修改建议调整设计...[/yellow]"
                                )
                                novel_ctx.snapshot.user_guidance = (
                                    f"{novel_ctx.snapshot.user_guidance}\n"
                                    f"修改意见: {feedback}"
                                )
                                generator.coordinator.state_manager.save_draft(
                                    novel_ctx.snapshot
                                )
                                with console.status(
                                    "[bold blue]重新设计中...[/bold blue]"
                                ):
                                    result = await generator.design()
                                if result.success:
                                    console.print(
                                        Panel(
                                            result.content,
                                            title="📋 调整后的设计",
                                        )
                                    )
                                    continue  # 继续等待用户确认
                                else:
                                    console.print(
                                        f"[red]调整失败: {result.error}[/red]"
                                    )
                                    continue
                        elif user_input in ["重做", "r", "redo"]:
                            console.print("\n[yellow]正在重新设计...[/yellow]")
                            novel_ctx.snapshot.global_summary = ""
                            generator.coordinator.state_manager.save_draft(
                                novel_ctx.snapshot
                            )
                            with console.status(
                                "[bold blue]重新设计中...[/bold blue]"
                            ):
                                result = await generator.design()
                            if result.success:
                                console.print(
                                    Panel(
                                        result.content,
                                        title="📋 新的设计结果",
                                    )
                                )
                                continue  # 继续等待用户确认
                            else:
                                console.print(
                                    f"[red]重做失败: {result.error}[/red]"
                                )
                                continue
                        elif user_input in ["取消", "c", "cancel", "q"]:
                            console.print("[yellow]已取消设计[/yellow]")
                            return 1
                else:
                    # 设计完成后显示蓝图
                    console.print("[green]✓ 设计完成![/green]")
                    console.print(
                        Panel(
                            result.content,
                            title="📋 设计蓝图",
                            border_style="green",
                        )
                    )
            else:
                console.print(f"[red]设计失败: {result.error}[/red]")
                return 1

        generator.save_checkpoint()

    except Exception as e:
        console.print(f"[red]错误: {e}[/red]")
        return 1
    finally:
        await generator.close()

    return 0


async def cmd_design(args: argparse.Namespace) -> int:
    """执行架构设计"""
    from src.agent import EditMode, HumanLoopManager
    from src.generator import NovelGenerator

    llm_config = get_llm_config()

    if not llm_config.get("api_key"):
        console.print("[red]错误: 未配置 API Key[/red]")
        return 1

    edit_mode = EditMode(getattr(args, "edit_mode", "auto"))
    auto_confirm = getattr(args, "auto_confirm", False)
    human_loop = HumanLoopManager(
        edit_mode=edit_mode,
        auto_confirm=auto_confirm or not args.interactive,
    )

    generator = NovelGenerator(
        llm_config=llm_config,
        save_dir=args.save_dir or "./novels",
    )

    try:
        novel_ctx = await generator.load_novel(args.title)

        if not novel_ctx:
            console.print(f"[red]错误: 未找到小说 '{args.title}'[/red]")
            return 1

        # 从现有内容构建设计（保留现有设计作为参考）
        existing_content = None
        existing_design = None
        if getattr(args, "from_content", False):
            completed = novel_ctx.snapshot.progress.completed_chapters
            if not completed:
                console.print("[yellow]该小说没有已完成的章节，无法从内容构建设计[/yellow]")
                return 1

            # 读取现有设计（作为参考，不清除）
            if novel_ctx.global_summary:
                existing_design = novel_ctx.global_summary
                console.print("[cyan]将参考现有设计主线...[/cyan]")

            # 读取已完成章节
            console.print(f"[cyan]正在读取 {len(completed)} 个已完成章节...[/cyan]")
            chapters_content = {}
            for ch_num in sorted(completed):
                content = generator.coordinator.state_manager.load_chapter(
                    args.title, ch_num
                )
                if content:
                    chapters_content[ch_num] = content

            if chapters_content:
                existing_content = chapters_content
                ch_count = len(chapters_content)
                msg = f"结合现有设计和 {ch_count} 章内容重构..."
                console.print(f"[cyan]{msg}[/cyan]")
                novel_ctx.snapshot.global_summary = ""
                novel_ctx.global_summary = ""

        if args.force:
            novel_ctx.snapshot.global_summary = ""
            novel_ctx.global_summary = ""
            console.print("[yellow]已清除旧的设计，将重新设计...[/yellow]")

        old_chapters = novel_ctx.snapshot.progress.total_chapters
        need_expand = False
        if args.chapters and args.chapters != old_chapters:
            novel_ctx.snapshot.progress.total_chapters = args.chapters
            generator.coordinator.state_manager.save_draft(novel_ctx.snapshot)
            console.print(f"[cyan]目标章节数: {old_chapters} → {args.chapters}[/cyan]")
            if novel_ctx.global_summary:
                need_expand = True
                console.print("[cyan]将在现有设计基础上扩展章节规划...[/cyan]")

        if novel_ctx.global_summary and not args.force and not need_expand:
            console.print(
                f"[yellow]《{args.title}》已有设计，使用 "
                f"[bold]design --force[/bold] 强制重新设计[/yellow]"
            )
            return 0

        if need_expand:
            novel_ctx.snapshot.user_guidance = (
                f"{novel_ctx.snapshot.user_guidance}\n"
                f"[扩展任务] 原有{old_chapters}章，现在需要扩展到{args.chapters}章，"
                f"请在保留原有核心设定和已完成章节规划的基础上，扩展后续章节大纲。"
            )
            generator.coordinator.state_manager.save_draft(novel_ctx.snapshot)

        with console.status(
            f"[bold blue]🎨 正在为《{args.title}》进行架构设计...[/bold blue]"
        ):
            result = await generator.design(
                existing_content=existing_content,
                existing_design=existing_design,
            )

        if result.success:
            console.print(
                Panel(
                    result.content,
                    title="📋 设计结果",
                    border_style="blue",
                )
            )

            if args.interactive:
                interaction = human_loop.confirm(
                    content=result.content,
                    title="设计结果",
                    allow_edit=True,
                )

                if not interaction.confirmed:
                    console.print("[yellow]已取消设计[/yellow]")
                    return 1

                if interaction.modified:
                    result.content = interaction.content
                    novel_ctx.snapshot.global_summary = interaction.content
                    generator.coordinator.state_manager.save_draft(novel_ctx.snapshot)
                    console.print("[green]✓ 设计已更新![/green]")

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(result.content)
                console.print(f"[dim]设计结果已保存到: {args.output}[/dim]")
            else:
                console.print("\n[green]✓ 设计完成![/green]\n")

        else:
            console.print(f"[red]设计失败: {result.error}[/red]")
            return 1

        generator.save_checkpoint()

    except Exception as e:
        console.print(f"[red]错误: {e}[/red]")
        return 1
    finally:
        await generator.close()

    return 0


async def cmd_write(args: argparse.Namespace) -> int:
    """撰写章节"""
    from src.generator import NovelGenerator

    llm_config = get_llm_config()

    if not llm_config.get("api_key"):
        console.print("[red]错误: 未配置 API Key[/red]")
        return 1

    generator = NovelGenerator(
        llm_config=llm_config,
        save_dir=args.save_dir or "./novels",
    )

    def on_progress(stage: str, message: str):
        if args.verbose:
            console.print(f"[dim]  {message}[/dim]")

    generator.on_progress(on_progress)

    try:
        novel_ctx = await generator.load_novel(args.title)

        if not novel_ctx:
            console.print(f"[red]❌ 未找到小说 '{args.title}'[/red]")
            return 1

        total = novel_ctx.snapshot.progress.total_chapters

        if args.all:
            # 从成品章节获取已写章节
            chapters = generator.coordinator.state_manager.list_chapters(args.title)
            max_chapter = max((c["chapter_num"] for c in chapters), default=0)

            start = max_chapter + 1
            if start > total:
                console.print("[green]✅ 所有章节已完成![/green]")
                return 0

            console.print(
                Panel(
                    f"[bold]撰写第 {start} 到 {total} 章[/bold]",
                    title="📝 批量写作",
                    border_style="blue",
                )
            )

            # 用于进度条更新
            progress_obj = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
            )
            progress_obj.start()
            task = progress_obj.add_task(
                "[cyan]写作进度", total=total - start + 1
            )

            # 章节完成回调 - 实时更新进度条
            def on_chapter_done(ch_num: int, content: str):
                progress_obj.advance(task)
                title_display = "无题"
                content_len = len(content) if content else 0
                console.print(
                    f"  [green]✓[/green] 第 {ch_num} 章 "
                    f"「[bold]{title_display}[/bold]」({content_len} 字)"
                )

            generator.on_chapter_complete(on_chapter_done)

            try:
                results = await generator.write_all_chapters(
                    start=start,
                    auto_audit=not args.no_audit,
                    auto_polish=not args.no_polish,
                )

                for result in results:
                    if not result.success:
                        console.print(
                            f"  [red]✗[/red] 第 {result.chapter_num} 章"
                            f"失败: {result.error}"
                        )
                        progress_obj.stop()
                        return 1

            except KeyboardInterrupt:
                console.print("\n[yellow]⚠️ 用户中断，正在保存进度...[/yellow]")
                generator.save_checkpoint()
                console.print("[green]✓ 进度已保存，可使用 -a 继续写作[/green]")
                progress_obj.stop()
                return 130
            finally:
                progress_obj.stop()

            console.print("\n[green]✅ 批量写作完成![/green]")
        else:
            chapter_num = args.chapter

            if chapter_num > total:
                console.print(
                    f"[red]❌ 章节号 {chapter_num} 超出范围 (总共 {total} 章)[/red]"
                )
                return 1

            with console.status(
                f"[bold blue]✍️ 正在撰写第 {chapter_num} 章...[/bold blue]"
            ):
                result = await generator.write_chapter(
                    chapter_num=chapter_num,
                    auto_audit=not args.no_audit,
                    auto_polish=not args.no_polish,
                )

            if result.success:
                title_display = result.chapter_title or "无题"
                content_len = len(result.content) if result.content else 0

                console.print(
                    Panel(
                        (
                            result.content[:1000] + "..."
                            if len(result.content) > 1000
                            else result.content
                        ),
                        title=(
                            f"📖 第 {chapter_num} 章 "
                            f"「{title_display}」({content_len} 字)"
                        ),
                        border_style="green",
                    )
                )

                if args.output:
                    with open(args.output, "w", encoding="utf-8") as f:
                        f.write(result.content or "")
                    print(f"  📄 已保存到: {args.output}")
            else:
                print(f"❌ 写作失败: {result.error}")
                return 1

        generator.save_checkpoint()

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ 用户中断[/yellow]")
        return 130
    except ConnectionError as e:
        console.print(f"[red]❌ 网络连接错误: {e}[/red]")
        console.print("[dim]提示: 请检查网络连接或稍后重试[/dim]")
        return 1
    except TimeoutError:
        console.print("[red]❌ 请求超时[/red]")
        console.print("[dim]提示: 请检查网络连接或稍后重试[/dim]")
        return 1
    except Exception as e:
        error_str = str(e).lower()
        if "401" in error_str or "unauthorized" in error_str:
            console.print("[red]❌ API Key 无效或已过期[/red]")
            console.print("[dim]提示: 请使用 'novel config --api-key' 更新密钥[/dim]")
        elif "429" in error_str or "rate limit" in error_str:
            console.print("[red]❌ API 请求频率超限[/red]")
            console.print("[dim]提示: 请等待几分钟后重试[/dim]")
        elif "500" in error_str or "502" in error_str or "503" in error_str:
            console.print("[red]❌ API 服务暂时不可用[/red]")
            console.print("[dim]提示: 请稍后重试[/dim]")
        elif "insufficient" in error_str or "quota" in error_str:
            console.print("[red]❌ API 配额不足[/red]")
            console.print("[dim]提示: 请检查账户余额[/dim]")
        else:
            console.print(f"[red]❌ 错误: {e}[/red]")
        return 1
    finally:
        await generator.close()

    return 0


async def cmd_list(args: argparse.Namespace) -> int:
    """列出小说/章节"""
    from src.core import NovelStateManager

    state_manager = NovelStateManager(args.save_dir or "./novels")

    if args.title:
        chapters = state_manager.list_chapters(args.title)

        if not chapters:
            console.print(f"[yellow]📚 小说《{args.title}》暂无完成章节[/yellow]")
            return 0

        table = Table(
            title=f"📚 《{args.title}》已完成章节",
            show_header=True,
            header_style="bold cyan",
            border_style="blue",
        )
        table.add_column("章节", style="dim", width=8)
        table.add_column("标题", style="bold")
        table.add_column("字数", justify="right", style="green")

        for ch in chapters:
            title = ch.get("title", "无题")
            table.add_row(
                f"第 {ch['chapter_num']} 章",
                title,
                f"{ch['word_count']} 字",
            )

        console.print(table)

    else:
        novels = state_manager.list_novels()

        if not novels:
            console.print("[yellow]📚 暂无小说[/yellow]")
            return 0

        table = Table(
            title="📚 已创建的小说",
            show_header=True,
            header_style="bold cyan",
            border_style="blue",
        )
        table.add_column("书名", style="bold magenta")
        table.add_column("章节数", justify="right")
        table.add_column("总字数", justify="right", style="green")
        table.add_column("状态", style="yellow")

        for novel in novels:
            total = (
                novel.get("last_draft", {}).get("total_chapters", 0)
                if novel.get("last_draft")
                else 0
            )
            is_complete = total > 0 and novel["chapter_count"] >= total
            status = "✅ 完成" if is_complete else "📝 写作中"
            table.add_row(
                novel["title"],
                str(novel["chapter_count"]),
                f"{novel['total_words']} 字",
                status,
            )

        console.print(table)

    return 0


async def cmd_status(args: argparse.Namespace) -> int:
    """查看小说状态"""
    from src.core import NovelStateManager

    state_manager = NovelStateManager(args.save_dir or "./novels")

    snapshot = state_manager.load_latest_draft(args.title)

    if not snapshot:
        console.print(f"[red]❌ 未找到小说: {args.title}[/red]")
        return 1

    # 基础信息面板
    info_text = Text()
    info_text.append("ID: ", style="dim")
    info_text.append(f"{snapshot.id}\n")
    info_text.append("创建: ", style="dim")
    info_text.append(f"{snapshot.created_at[:10] if snapshot.created_at else '未知'}\n")
    info_text.append("更新: ", style="dim")
    info_text.append(f"{snapshot.updated_at[:10] if snapshot.updated_at else '未知'}\n")
    info_text.append("阶段: ", style="dim")
    info_text.append(f"{snapshot.progress.current_phase.value}\n")
    info_text.append("进度: ", style="dim")
    info_text.append(
        f"{snapshot.progress.current_chapter}/"
        f"{snapshot.progress.total_chapters} 章\n"
    )

    # 完成章节
    if snapshot.progress.completed_chapters:
        completed = sorted(snapshot.progress.completed_chapters)
        info_text.append("完成: ", style="dim")
        info_text.append(f"{len(completed)} 章 ")
        if len(completed) <= 10:
            info_text.append(f"[{', '.join(map(str, completed))}]", style="green")
        else:
            first_five = ', '.join(map(str, completed[:5]))
            last_three = ', '.join(map(str, completed[-3:]))
            info_text.append(f"[{first_five} ... {last_three}]", style="green")

    console.print(
        Panel(
            info_text,
            title=f"[bold cyan]《{snapshot.title}》[/bold cyan]",
            border_style="blue",
        )
    )

    # 设计蓝图
    if snapshot.global_summary:
        print(f"\n{'─' * 50}")
        print("  📋 设计蓝图")
        print(f"{'─' * 50}")
        summary = snapshot.global_summary

        if args.full:
            # 显示完整蓝图
            for line in summary.split("\n"):
                print(f"  {line}")
        else:
            # 显示摘要
            if len(summary) > 800:
                lines = summary.split("\n")
                key_lines = []
                capture = True
                for line in lines[:50]:
                    if "【blueprint】" in line:
                        capture = False
                        key_lines.append("  ... (章节蓝图已省略，使用 --full 查看)")
                        break
                    if capture and line.strip():
                        key_lines.append(f"  {line}")
                print("\n".join(key_lines[:20]))
                console.print("\n[dim]💡 使用 --full 查看完整设计[/dim]")
            else:
                for line in summary.split("\n")[:30]:
                    print(f"  {line}")
    else:
        # 设计蓝图为空时的提示
        console.print(
            Panel(
                "[yellow]⚠️ 尚未进行设计[/yellow]\n\n"
                "请运行以下命令进行设计:\n"
                f"  [cyan]novel design {snapshot.title}[/cyan]",
                title="📋 设计蓝图",
                border_style="yellow",
            )
        )

    # 时间轴摘要
    if snapshot.timeline_data and snapshot.timeline_data.get("points"):
        points = snapshot.timeline_data.get("points", {})
        point_count = len(points)

        timeline_table = Table(
            title="⏱️ 时间轴",
            show_header=False,
            border_style="dim",
            box=None,
            padding=(0, 2),
        )
        timeline_table.add_column("info", style="dim")

        timeline_table.add_row(f"已记录 {point_count} 个时间点")

        if point_count <= 5:
            for pid, p in list(points.items())[:5]:
                timeline_table.add_row(f"• {p.get('label', pid)}")

        console.print(timeline_table)

    # 角色摘要
    if snapshot.characters_data:
        char_count = len(snapshot.characters_data)

        char_table = Table(
            title="👥 角色",
            show_header=False,
            border_style="dim",
            box=None,
            padding=(0, 2),
        )
        char_table.add_column("info")

        char_table.add_row(f"已设定 {char_count} 个角色")

        if char_count <= 6:
            for cid, char in snapshot.characters_data.items():
                name = char.get("name", cid)
                role = char.get("attrs", {}).get("role", "")
                if role:
                    char_table.add_row(f"• [bold]{name}[/bold] ([dim]{role}[/dim])")
                else:
                    char_table.add_row(f"• [bold]{name}[/bold]")

        console.print(char_table)

    return 0


async def cmd_export(args: argparse.Namespace) -> int:
    """导出小说"""
    from src.core import NovelStateManager

    state_manager = NovelStateManager(args.save_dir or "./novels")

    chapters = state_manager.list_chapters(args.title)

    if not chapters:
        console.print(f"[yellow]小说《{args.title}》暂无完成章节[/yellow]")
        return 1

    # 按章节排序
    chapters.sort(key=lambda x: x["chapter_num"])

    output_path = args.output or f"{args.title}.txt"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]导出中...", total=None)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"{args.title}\n\n")

            for ch in chapters:
                content = state_manager.load_chapter(args.title, ch["chapter_num"])
                if content:
                    title = ch.get("title", f"第{ch['chapter_num']}章")
                    f.write(f"第{ch['chapter_num']}章 {title}\n\n")
                    f.write(content)
                    f.write("\n\n")

        progress.update(task, description="[green]导出完成!")

    console.print(
        Panel(
            f"[bold green]✓ 导出成功[/bold green]\n\n"
            f"文件: [cyan]{output_path}[/cyan]\n"
            f"章节: [bold]{len(chapters)}[/bold] 章",
            border_style="green",
        )
    )

    return 0


def main() -> int:
    """主入口"""
    parser = argparse.ArgumentParser(
        prog="novel",
        description="AI 小说生成器命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 全局参数
    parser.add_argument(
        "--edit-mode",
        choices=["cli", "editor", "auto"],
        default="auto",
        help="编辑模式: cli(命令行)/editor(编辑器)/auto(自动选择)",
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="自动确认，跳过所有交互",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # config 命令
    config_parser = subparsers.add_parser("config", help="配置 API")
    config_parser.add_argument("--api-key", help="API Key")
    config_parser.add_argument("--base-url", help="API Base URL")
    config_parser.add_argument("--model", help="默认模型")
    config_parser.add_argument(
        "--llm-type", help="LLM 类型 (openai/deepseek/compatible)"
    )

    # create 命令
    create_parser = subparsers.add_parser("create", help="创建新小说")
    create_parser.add_argument("title", help="小说标题")
    create_parser.add_argument("--prompt", "-p", required=True, help="小说需求描述")
    create_parser.add_argument(
        "--chapters", "-c", type=int, default=20, help="总章节数 (默认: 20)"
    )
    create_parser.add_argument(
        "--words", "-w", type=int, default=3000, help="每章字数 (默认: 3000)"
    )
    create_parser.add_argument(
        "--design", "-d", action="store_true", help="创建后立即设计"
    )
    create_parser.add_argument(
        "--interactive", "-i", action="store_true", help="交互模式，设计后等待确认"
    )
    create_parser.add_argument("--save-dir", help="保存目录")
    create_parser.add_argument("--db", help="知识库数据库路径")
    create_parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    # design 命令
    design_parser = subparsers.add_parser("design", help="执行架构设计")
    design_parser.add_argument("title", help="小说标题")
    design_parser.add_argument("--output", "-o", help="输出文件")
    design_parser.add_argument(
        "--interactive", "-i", action="store_true", help="交互模式"
    )
    design_parser.add_argument(
        "--chapters", "-c", type=int, help="目标章节数 (默认使用创建时的设置)"
    )
    design_parser.add_argument(
        "--force", "-f", action="store_true", help="强制重新设计，清除旧设计"
    )
    design_parser.add_argument(
        "--from-content", action="store_true",
        help="从现有章节正文反向构建设计（适用于旧版小说）"
    )
    design_parser.add_argument("--save-dir", help="保存目录")

    # write 命令
    write_parser = subparsers.add_parser("write", help="撰写章节")
    write_parser.add_argument("title", help="小说标题")
    write_parser.add_argument(
        "--chapter", "-c", type=int, help="章节号 (不指定则续写下一章)"
    )
    write_parser.add_argument(
        "--all", "-a", action="store_true", help="撰写所有剩余章节"
    )
    write_parser.add_argument("--no-audit", action="store_true", help="跳过审计")
    write_parser.add_argument("--no-polish", action="store_true", help="跳过润色")
    write_parser.add_argument(
        "--interactive", "-i", action="store_true", help="交互模式，章节预览"
    )
    write_parser.add_argument("--output", "-o", help="输出文件")
    write_parser.add_argument("--save-dir", help="保存目录")
    write_parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出小说/章节")
    list_parser.add_argument("title", nargs="?", help="小说标题 (不指定则列出所有小说)")
    list_parser.add_argument("--save-dir", help="保存目录")

    # status 命令
    status_parser = subparsers.add_parser("status", help="查看小说状态")
    status_parser.add_argument("title", help="小说标题")
    status_parser.add_argument(
        "--full", "-f", action="store_true", help="显示完整设计蓝图"
    )
    status_parser.add_argument("--save-dir", help="保存目录")

    # export 命令
    export_parser = subparsers.add_parser("export", help="导出小说")
    export_parser.add_argument("title", help="小说标题")
    export_parser.add_argument("--output", "-o", help="输出文件")
    export_parser.add_argument("--save-dir", help="保存目录")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # 路由到对应命令
    commands = {
        "config": cmd_config,
        "create": cmd_create,
        "design": cmd_design,
        "write": cmd_write,
        "list": cmd_list,
        "status": cmd_status,
        "export": cmd_export,
    }

    if args.command in commands:
        return asyncio.run(commands[args.command](args))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
