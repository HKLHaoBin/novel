#!/usr/bin/env python3
"""小说生成器命令行工具"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# 默认配置路径
DEFAULT_CONFIG_PATH = Path.home() / ".novel" / "config.json"


def load_config() -> dict[str, Any]:
    """加载配置文件"""
    config_path = DEFAULT_CONFIG_PATH
    
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
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
        print(f"已设置 Base URL: {args.base_url}")
    
    if args.model:
        config["model"] = args.model
        print(f"已设置模型: {args.model}")
    
    if args.llm_type:
        config["llm_type"] = args.llm_type
        print(f"已设置 LLM 类型: {args.llm_type}")
    
    if config:
        save_config(config)
        print(f"配置已保存到: {DEFAULT_CONFIG_PATH}")
    else:
        # 显示当前配置
        print("当前配置:")
        for key, value in config.items():
            if key == "api_key" and value:
                print(f"  {key}: {value[:8]}...")
            else:
                print(f"  {key}: {value}")
    
    return 0


async def cmd_create(args: argparse.Namespace) -> int:
    """创建小说"""
    from src.generator import NovelGenerator
    
    llm_config = get_llm_config()
    
    if not llm_config.get("api_key"):
        print("错误: 未配置 API Key，请先运行 'novel config --api-key YOUR_KEY'")
        return 1
    
    generator = NovelGenerator(
        llm_config=llm_config,
        save_dir=args.save_dir or "./novels",
        knowledge_db=args.db or "./novel_memory.db",
    )
    
    def on_progress(stage: str, message: str):
        if args.verbose:
            print(f"[{stage}] {message}")
    
    generator.on_progress(on_progress)
    
    try:
        novel_ctx = await generator.create_novel(
            title=args.title,
            user_prompt=args.prompt,
            total_chapters=args.chapters,
            word_count_per_chapter=args.words,
        )
        
        print(f"\n已创建小说: {novel_ctx.snapshot.title}")
        print(f"ID: {novel_ctx.snapshot.id}")
        print(f"章节数: {args.chapters}")
        print(f"每章字数: {args.words}")
        
        if args.design:
            print("\n开始架构设计...")
            result = await generator.design()
            
            if result.success:
                if args.interactive:
                    # 交互模式：显示设计结果并等待用户确认
                    print("\n" + "="*60)
                    print("设计结果预览:")
                    print("="*60)
                    print(result.content)
                    print("="*60)
                    
                    while True:
                        user_input = input("\n选项: [确认/修改/重做/取消]: ").strip().lower()
                        
                        if user_input in ["确认", "y", "yes", "ok"]:
                            print("设计已确认!")
                            break
                        elif user_input in ["修改", "m", "modify"]:
                            print("\n请输入修改建议（输入空行结束）:")
                            lines = []
                            while True:
                                line = input()
                                if not line:
                                    break
                                lines.append(line)
                            
                            if lines:
                                modification = "\n".join(lines)
                                print("\n正在根据修改建议调整设计...")
                                # 重新设计，带上修改意见
                                result = await generator.design()
                                if result.success:
                                    print("\n调整后的设计:")
                                    print(result.content)
                                else:
                                    print(f"调整失败: {result.error}")
                        elif user_input in ["重做", "r", "redo"]:
                            print("\n正在重新设计...")
                            result = await generator.design()
                            if result.success:
                                print("\n新的设计结果:")
                                print(result.content)
                            else:
                                print(f"重做失败: {result.error}")
                        elif user_input in ["取消", "c", "cancel", "q"]:
                            print("已取消设计")
                            return 1
                else:
                    print("设计完成!")
                    if args.verbose:
                        print(result.content[:500] + "...")
            else:
                print(f"设计失败: {result.error}")
                return 1
        
        # 保存检查点
        generator.save_checkpoint()
        
    except Exception as e:
        print(f"错误: {e}")
        return 1
    finally:
        await generator.close()
    
    return 0


async def cmd_design(args: argparse.Namespace) -> int:
    """执行架构设计"""
    from src.generator import NovelGenerator
    
    llm_config = get_llm_config()
    
    if not llm_config.get("api_key"):
        print("错误: 未配置 API Key")
        return 1
    
    generator = NovelGenerator(
        llm_config=llm_config,
        save_dir=args.save_dir or "./novels",
    )
    
    try:
        # 加载小说
        novel_ctx = await generator.load_novel(args.title)
        
        if not novel_ctx:
            print(f"错误: 未找到小说 '{args.title}'")
            return 1
        
        print(f"正在为《{args.title}》进行架构设计...")
        
        result = await generator.design()
        
        if result.success:
            if args.interactive:
                # 交互模式
                print("\n" + "="*60)
                print("设计结果:")
                print("="*60)
                print(result.content)
                print("="*60)
                
                while True:
                    user_input = input("\n选项: [确认/修改/重做/取消]: ").strip().lower()
                    
                    if user_input in ["确认", "y", "yes", "ok"]:
                        print("设计已确认!")
                        break
                    elif user_input in ["修改", "m", "modify"]:
                        print("\n请输入修改建议（输入空行结束）:")
                        lines = []
                        while True:
                            line = input()
                            if not line:
                                break
                            lines.append(line)
                        
                        if lines:
                            print("\n正在根据修改建议调整设计...")
                            result = await generator.design()
                            if result.success:
                                print("\n调整后的设计:")
                                print(result.content)
                            else:
                                print(f"调整失败: {result.error}")
                    elif user_input in ["重做", "r", "redo"]:
                        print("\n正在重新设计...")
                        result = await generator.design()
                        if result.success:
                            print("\n新的设计结果:")
                            print(result.content)
                        else:
                            print(f"重做失败: {result.error}")
                    elif user_input in ["取消", "c", "cancel", "q"]:
                        print("已取消设计")
                        return 1
            
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(result.content)
                print(f"设计结果已保存到: {args.output}")
            elif not args.interactive:
                print("\n设计完成!\n")
                print(result.content)
        else:
            print(f"设计失败: {result.error}")
            return 1
        
        generator.save_checkpoint()
        
    except Exception as e:
        print(f"错误: {e}")
        return 1
    finally:
        await generator.close()
    
    return 0


async def cmd_write(args: argparse.Namespace) -> int:
    """撰写章节"""
    from src.generator import NovelGenerator
    
    llm_config = get_llm_config()
    
    if not llm_config.get("api_key"):
        print("错误: 未配置 API Key")
        return 1
    
    generator = NovelGenerator(
        llm_config=llm_config,
        save_dir=args.save_dir or "./novels",
        knowledge_db=args.db or "./novel_memory.db",
    )
    
    def on_progress(stage: str, message: str):
        print(f"[{stage}] {message}")
    
    generator.on_progress(on_progress)
    
    try:
        # 加载小说
        novel_ctx = await generator.load_novel(args.title)
        
        if not novel_ctx:
            print(f"错误: 未找到小说 '{args.title}'")
            return 1
        
        total = novel_ctx.snapshot.progress.total_chapters
        
        if args.all:
            # 写全部章节
            start = novel_ctx.snapshot.progress.current_chapter + 1
            if start > total:
                print("所有章节已完成!")
                return 0
            
            print(f"开始撰写第 {start} 到 {total} 章...")
            
            results = await generator.write_all_chapters(
                start=start,
                auto_audit=not args.no_audit,
                auto_polish=not args.no_polish,
            )
            
            for result in results:
                if result.success:
                    print(f"\n第 {result.chapter_num} 章「{result.chapter_title}」完成 ({len(result.content)} 字)")
                else:
                    print(f"\n第 {result.chapter_num} 章失败: {result.error}")
                    return 1
        else:
            # 写单章
            chapter_num = args.chapter
            
            if chapter_num > total:
                print(f"错误: 章节号 {chapter_num} 超出范围 (总共 {total} 章)")
                return 1
            
            result = await generator.write_chapter(
                chapter_num=chapter_num,
                auto_audit=not args.no_audit,
                auto_polish=not args.no_polish,
            )
            
            if result.success:
                print(f"\n第 {chapter_num} 章「{result.chapter_title}」完成 ({len(result.content)} 字)")
                
                if args.output:
                    with open(args.output, "w", encoding="utf-8") as f:
                        f.write(result.content)
                    print(f"已保存到: {args.output}")
            else:
                print(f"写作失败: {result.error}")
                return 1
        
        generator.save_checkpoint()
        
    except Exception as e:
        print(f"错误: {e}")
        return 1
    finally:
        await generator.close()
    
    return 0


async def cmd_list(args: argparse.Namespace) -> int:
    """列出小说/章节"""
    from src.core import NovelStateManager
    
    state_manager = NovelStateManager(args.save_dir or "./novels")
    
    if args.title:
        # 列出章节
        chapters = state_manager.list_chapters(args.title)
        
        if not chapters:
            print(f"小说《{args.title}》暂无完成章节")
            return 0
        
        print(f"《{args.title}》已完成章节:\n")
        for ch in chapters:
            print(f"  第 {ch['chapter_num']} 章: {ch['title']} ({ch['word_count']} 字)")
    else:
        # 列出小说
        novels = state_manager.list_novels()
        
        if not novels:
            print("暂无小说")
            return 0
        
        print("已创建的小说:\n")
        for novel in novels:
            print(f"  《{novel['title']}》 - {novel['chapter_count']} 章 ({novel['total_words']} 字)")
    
    return 0


async def cmd_status(args: argparse.Namespace) -> int:
    """查看小说状态"""
    from src.core import NovelStateManager
    
    state_manager = NovelStateManager(args.save_dir or "./novels")
    
    snapshot = state_manager.load_latest_draft(args.title)
    
    if not snapshot:
        print(f"未找到小说: {args.title}")
        return 1
    
    print(f"\n《{snapshot.title}》状态报告\n")
    print(f"ID: {snapshot.id}")
    print(f"创建时间: {snapshot.created_at}")
    print(f"更新时间: {snapshot.updated_at}")
    print(f"阶段: {snapshot.progress.current_phase.value}")
    print(f"进度: {snapshot.progress.current_chapter}/{snapshot.progress.total_chapters} 章")
    print(f"已完成章节: {len(snapshot.progress.completed_chapters)} 章")
    
    if snapshot.progress.completed_chapters:
        print(f"\n已完成: {', '.join(map(str, sorted(snapshot.progress.completed_chapters)))} 章")
    
    return 0


async def cmd_export(args: argparse.Namespace) -> int:
    """导出小说"""
    from src.core import NovelStateManager
    
    state_manager = NovelStateManager(args.save_dir or "./novels")
    
    chapters = state_manager.list_chapters(args.title)
    
    if not chapters:
        print(f"小说《{args.title}》暂无完成章节")
        return 1
    
    # 按章节排序
    chapters.sort(key=lambda x: x["chapter_num"])
    
    output_path = args.output or f"{args.title}.txt"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"{args.title}\n\n")
        
        for ch in chapters:
            content = state_manager.load_chapter(args.title, ch["chapter_num"])
            if content:
                title = ch.get("title", f"第{ch['chapter_num']}章")
                f.write(f"第{ch['chapter_num']}章 {title}\n\n")
                f.write(content)
                f.write("\n\n")
    
    print(f"已导出到: {output_path}")
    print(f"共 {len(chapters)} 章")
    
    return 0


def main() -> int:
    """主入口"""
    parser = argparse.ArgumentParser(
        prog="novel",
        description="AI 小说生成器命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # config 命令
    config_parser = subparsers.add_parser("config", help="配置 API")
    config_parser.add_argument("--api-key", help="API Key")
    config_parser.add_argument("--base-url", help="API Base URL")
    config_parser.add_argument("--model", help="默认模型")
    config_parser.add_argument("--llm-type", help="LLM 类型 (openai/deepseek/compatible)")
    
    # create 命令
    create_parser = subparsers.add_parser("create", help="创建新小说")
    create_parser.add_argument("title", help="小说标题")
    create_parser.add_argument("--prompt", "-p", required=True, help="小说需求描述")
    create_parser.add_argument("--chapters", "-c", type=int, default=20, help="总章节数 (默认: 20)")
    create_parser.add_argument("--words", "-w", type=int, default=3000, help="每章字数 (默认: 3000)")
    create_parser.add_argument("--design", "-d", action="store_true", help="创建后立即设计")
    create_parser.add_argument("--interactive", "-i", action="store_true", help="交互模式，设计后等待确认")
    create_parser.add_argument("--save-dir", help="保存目录")
    create_parser.add_argument("--db", help="知识库数据库路径")
    create_parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    # design 命令
    design_parser = subparsers.add_parser("design", help="执行架构设计")
    design_parser.add_argument("title", help="小说标题")
    design_parser.add_argument("--output", "-o", help="输出文件")
    design_parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    design_parser.add_argument("--save-dir", help="保存目录")
    
    # write 命令
    write_parser = subparsers.add_parser("write", help="撰写章节")
    write_parser.add_argument("title", help="小说标题")
    write_parser.add_argument("--chapter", "-c", type=int, help="章节号 (不指定则续写下一章)")
    write_parser.add_argument("--all", "-a", action="store_true", help="撰写所有剩余章节")
    write_parser.add_argument("--no-audit", action="store_true", help="跳过审计")
    write_parser.add_argument("--no-polish", action="store_true", help="跳过润色")
    write_parser.add_argument("--output", "-o", help="输出文件")
    write_parser.add_argument("--save-dir", help="保存目录")
    write_parser.add_argument("--db", help="知识库数据库路径")
    
    # list 命令
    list_parser = subparsers.add_parser("list", help="列出小说/章节")
    list_parser.add_argument("title", nargs="?", help="小说标题 (不指定则列出所有小说)")
    list_parser.add_argument("--save-dir", help="保存目录")
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="查看小说状态")
    status_parser.add_argument("title", help="小说标题")
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
