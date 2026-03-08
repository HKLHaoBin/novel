"""LLM 提供者适配层 - 封装 intelligence 库"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.exceptions import convert_intelligence_error


class ToolProtocol(Protocol):
    """工具协议 - 定义工具的接口"""

    name: str
    description: str
    parameters: dict[str, str]

    def execute(self, context: Any, **kwargs: Any) -> "ToolResult": ...


class ProviderProtocol(Protocol):
    """提供者协议 - ToolCallLoop 需要的接口"""

    model: str

    def get_raw_provider(self) -> Any: ...


@dataclass
class ToolResult:
    """工具执行结果"""

    success: bool
    content: str
    issues: list[str] = field(default_factory=list)
    data: Any = None


# intelligence 库的导入
try:
    from dawn_shuttle.dawn_shuttle_intelligence import (
        AnthropicProvider,
        DeepSeekProvider,
        GenerateConfig,
        GoogleProvider,
        Message,
        MoonshotProvider,
        OpenAICompatibleProvider,
        OpenAIProvider,
        ToolCall,
        generate_text,
        stream_text,
    )

    INTELLIGENCE_AVAILABLE = True
except ImportError:
    INTELLIGENCE_AVAILABLE = False


def build_tool_definitions(tools: dict) -> list[dict]:
    """
    将工具字典转换为 OpenAI function calling 格式

    Args:
        tools: 工具字典 {name: Tool}

    Returns:
        OpenAI tools 格式的列表
    """
    definitions = []

    for name, tool in tools.items():
        # 构建参数 schema
        properties = {}
        required = []

        for param_name, param_desc in tool.parameters.items():
            properties[param_name] = {"type": "string", "description": param_desc}
            # 如果参数描述不包含"可选"，则视为必需
            if "可选" not in param_desc:
                required.append(param_name)

        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )

    return definitions


class ToolCallLoop:
    """工具调用循环管理器"""

    def __init__(
        self,
        tools: dict[str, ToolProtocol],
        context: Any,
        max_iterations: int = 10,
        on_tool_call: Callable[[str, dict], None] | None = None,
        mode: str = "write",  # "write" 或 "design"
    ):
        """
        初始化工具调用循环

        Args:
            tools: 工具字典
            context: 传递给工具的上下文
            max_iterations: 最大迭代次数
            on_tool_call: 工具调用回调
            mode: 模式（write 或 design）
        """
        self.tools = tools
        self.context = context
        self.max_iterations = max_iterations
        self.on_tool_call = on_tool_call
        self.final_content: str | None = None
        self.chapter_title: str | None = None
        self.mode = mode

    async def execute_tool(self, name: str, arguments: dict) -> ToolResult:
        """执行单个工具"""
        if name not in self.tools:
            return ToolResult(
                success=False,
                content=f"错误: 未知工具 '{name}'",
                issues=[f"可用工具: {', '.join(self.tools.keys())}"],
            )

        tool = self.tools[name]
        try:
            # 支持同步和异步工具
            import asyncio

            if asyncio.iscoroutinefunction(tool.execute):
                result: ToolResult = await tool.execute(self.context, **arguments)
            else:
                result = tool.execute(self.context, **arguments)

            if self.on_tool_call:
                self.on_tool_call(name, arguments)

            # 检测 complete/complete_design 调用
            if name in ("complete", "complete_design") and result.success:
                # 优先从 result.data 获取（工具放在那里）
                if result.data and "final_content" in result.data:
                    self.final_content = result.data["final_content"]
                    # 同时获取标题
                    if result.data.get("chapter_title"):
                        self.chapter_title = result.data["chapter_title"]
                else:
                    # 回退到从参数获取
                    self.final_content = arguments.get("content", "")
                    if arguments.get("title"):
                        self.chapter_title = arguments.get("title")

            # 检测 set_chapter_title 调用
            if name == "set_chapter_title" and result.success:
                if result.data and result.data.get("chapter_title"):
                    self.chapter_title = result.data["chapter_title"]
                elif arguments.get("title"):
                    self.chapter_title = arguments.get("title")

            return result
        except Exception as e:
            import traceback

            return ToolResult(
                success=False,
                content=f"工具执行错误: {e!s}",
                issues=[traceback.format_exc()],
            )

    async def run(
        self,
        provider: ProviderProtocol,
        system_prompt: str,
        user_prompt: str,
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """
        运行工具调用循环

        Args:
            provider: LLM 提供者
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            model: 模型名称
            temperature: 温度
            max_tokens: 最大 token

        Returns:
            最终生成的内容
        """
        # 构建工具定义
        tool_definitions = build_tool_definitions(self.tools)

        # 构建消息
        messages = []
        if system_prompt:
            messages.append(Message.system(system_prompt))
        messages.append(Message.user(user_prompt))

        iteration = 0
        max_retries = 3  # API 调用重试次数

        while iteration < self.max_iterations:
            iteration += 1

            # 调用 LLM（带重试）
            retry_count = 0
            while retry_count < max_retries:
                try:
                    response = await generate_text(
                        messages=messages,
                        provider=provider.get_raw_provider(),
                        model=model or provider.model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=tool_definitions if tool_definitions else None,
                    )
                    break  # 成功则跳出重试循环
                except Exception as e:
                    error_str = str(e).lower()
                    retry_count += 1
                    # 400 错误可能是临时问题，尝试重试
                    if "400" in error_str and retry_count < max_retries:
                        import asyncio

                        await asyncio.sleep(2**retry_count)  # 指数退避
                        continue
                    # 其他错误或重试次数用尽
                    raise

            # 检查是否有工具调用
            if response.tool_calls:
                # 添加助手消息
                # 需要将字典格式转换为 ToolCall 对象
                formatted_tool_calls = []
                for tc in response.tool_calls:
                    if isinstance(tc, dict):
                        formatted_tool_calls.append(
                            ToolCall(
                                id=tc.get("id", ""),
                                name=tc.get("name", ""),
                                arguments=tc.get("arguments", {}),
                            )
                        )
                    elif isinstance(tc, ToolCall):
                        formatted_tool_calls.append(tc)
                    else:
                        # 可能是其他对象格式
                        formatted_tool_calls.append(
                            ToolCall(
                                id=getattr(tc, "id", ""),
                                name=getattr(tc, "name", "")
                                or getattr(tc.function, "name", ""),
                                arguments=getattr(tc, "arguments", {})
                                or getattr(tc.function, "arguments", {}),
                            )
                        )

                messages.append(
                    Message.assistant(
                        content=response.text or "", tool_calls=formatted_tool_calls
                    )
                )

                # 执行每个工具调用
                for tool_call in response.tool_calls:
                    # intelligence 返回的是字典格式
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get("name", "")
                        tool_args = tool_call.get("arguments", {})
                        tool_id = tool_call.get("id", "")
                    elif isinstance(tool_call, ToolCall):
                        tool_name = tool_call.name
                        tool_args = tool_call.arguments
                        tool_id = tool_call.id
                    else:
                        tool_name = getattr(tool_call, "name", "") or getattr(
                            tool_call.function, "name", ""
                        )
                        tool_args = getattr(tool_call, "arguments", {}) or getattr(
                            tool_call.function, "arguments", {}
                        )
                        tool_id = getattr(tool_call, "id", "")

                    # 执行工具
                    tool_result = await self.execute_tool(tool_name, tool_args)

                    # 检测 complete/complete_design 调用
                    if (
                        tool_name in ("complete", "complete_design")
                        and self.final_content is not None
                    ):
                        return self.final_content

                    # 添加工具结果消息
                    messages.append(
                        Message.tool_result(
                            tool_call_id=tool_id,
                            content=tool_result.content
                            if hasattr(tool_result, "content")
                            else str(tool_result),
                        )
                    )

                # 继续循环让 LLM 处理工具结果
                continue

            # 没有工具调用
            # 重要：必须通过工具提交，不能直接返回 response.text
            if response.text and response.text.strip():
                # 根据模式给出不同提示
                if self.mode == "design" or "complete_design" in self.tools:
                    # 设计模式
                    messages.append(
                        Message.user(
                            "⚠️ 你必须使用工具来构建设计！\n"
                            "可用的设计工具：\n"
                            "- set_seed(core, conflict, theme, tone) - 设置故事核心\n"
                            "- add_character(name, role, appearances, ...) - 添加角色\n"
                            "- add_location(name, loc_type, chapters, ...) - 添加地点\n"
                            "- add_chapter(num, title, chars, locs, ...) - 添加章节\n"
                            "- complete_design(summary) - 完成设计\n\n"
                            "不要只输出文字描述！必须调用工具来存储设计数据！"
                        )
                    )
                else:
                    # 写作模式
                    messages.append(
                        Message.user(
                            "请使用 complete(content) 工具提交你的写作内容。"
                            "不要直接输出文本，必须调用 complete 工具！"
                        )
                    )
                continue

            # 完全没有响应，继续循环
            if self.mode == "design" or "complete_design" in self.tools:
                messages.append(
                    Message.user(
                        "请调用设计工具构建设计，"
                        "完成后调用 complete_design() 提交。"
                    )
                )
            else:
                messages.append(
                    Message.user("请继续工作，完成写作后调用 complete(content) 提交。")
                )

        if iteration >= self.max_iterations:
            # 达到最大迭代次数，要求 LLM 直接提交
            messages.append(
                Message.user(
                    "你已经收集了足够的上下文信息。"
                    "现在必须立即调用 complete(content) 提交你的写作内容！"
                    "不要再调用其他工具，直接提交你写好的章节内容。"
                )
            )
            # 带重试的调用
            retry_count = 0
            while retry_count < max_retries:
                try:
                    response = await generate_text(
                        messages=messages,
                        provider=provider.get_raw_provider(),
                        model=model or provider.model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=tool_definitions if tool_definitions else None,
                    )
                    break
                except Exception as e:
                    error_str = str(e).lower()
                    retry_count += 1
                    if "400" in error_str and retry_count < max_retries:
                        import asyncio

                        await asyncio.sleep(2**retry_count)
                        continue
                    raise
            # 检查这次是否调用了 complete
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    if isinstance(tool_call, dict):
                        tool_name = tool_call.get("name", "")
                        tool_args = tool_call.get("arguments", {})
                    else:
                        tool_name = getattr(tool_call, "name", "") or getattr(
                            tool_call.function, "name", ""
                        )
                        tool_args = getattr(tool_call, "arguments", {}) or getattr(
                            tool_call.function, "arguments", {}
                        )
                    if tool_name in ("complete", "complete_design"):
                        await self.execute_tool(tool_name, tool_args)
                        if self.final_content is not None:
                            return self.final_content

            # 如果 LLM 仍然没有调用 complete，检查是否有有效的文本内容
            # 注意：这可能是不完整的，但作为最后的回退
            if response.text and len(response.text.strip()) > 100:
                # 有足够的内容，可能是 LLM 直接返回了正文
                # 记录警告但返回内容
                import warnings

                warnings.warn(
                    "ToolCallLoop 达到最大迭代且 LLM 未调用 complete，"
                    "使用 response.text 作为回退内容",
                    RuntimeWarning,
                    stacklevel=2,
                )
                return response.text  # type: ignore[no-any-return]

            # 没有有效内容，返回错误指示
            return ""

        # 永远不会执行到这里，因为 while 循环只会在 iteration >= max_iterations 时退出
        # 而 if iteration >= self.max_iterations 块中有所有必要的 return
        return ""  # type: ignore[unreachable]


class LLMProvider:
    """LLM 提供者封装"""

    def __init__(
        self,
        provider_type: str = "deepseek",
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        **kwargs,
    ):
        """
        初始化 LLM 提供者

        Args:
            provider_type: 提供者类型
                (openai/anthropic/google/deepseek/moonshot/compatible)
            api_key: API 密钥
            base_url: 自定义 API 地址（可选）
            model: 默认模型
        """
        if not INTELLIGENCE_AVAILABLE:
            raise ImportError(
                "intelligence 库未安装，请确保 dawn_shuttle_intelligence 可用"
            )

        self.provider_type = provider_type
        self.model = model
        self._provider = self._create_provider(
            provider_type, api_key, base_url, **kwargs
        )

    def _create_provider(
        self, provider_type: str, api_key: str, base_url: str, **kwargs
    ):
        """创建底层 provider"""
        providers = {
            "openai": lambda: OpenAIProvider(
                api_key=api_key, base_url=base_url or None, **kwargs
            ),
            "anthropic": lambda: AnthropicProvider(api_key=api_key, **kwargs),
            "google": lambda: GoogleProvider(api_key=api_key, **kwargs),
            "deepseek": lambda: DeepSeekProvider(api_key=api_key, **kwargs),
            "moonshot": lambda: MoonshotProvider(api_key=api_key, **kwargs),
            "compatible": lambda: OpenAICompatibleProvider(
                api_key=api_key, base_url=base_url, **kwargs
            ),
        }

        if provider_type not in providers:
            raise ValueError(f"不支持的 provider 类型: {provider_type}")

        return providers[provider_type]()

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        **kwargs,
    ) -> str:
        """
        生成文本（简单接口）

        Args:
            prompt: 用户输入
            system: 系统提示词
            temperature: 温度
            max_tokens: 最大 token 数

        Returns:
            生成的文本

        Raises:
            NovelError: 转换后的自定义异常
        """
        messages = []
        if system:
            messages.append(Message.system(system))
        messages.append(Message.user(prompt))

        config = GenerateConfig(
            model=kwargs.get("model", self.model),
            temperature=temperature,
            max_tokens=max_tokens,
            **{k: v for k, v in kwargs.items() if k not in ["model"]},
        )

        try:
            response = await generate_text(
                messages=messages,
                provider=self._provider,
                **config.to_dict()
                if hasattr(config, "to_dict")
                else {"model": config.model},
            )
            return response.text  # type: ignore[no-any-return]
        except Exception as e:
            # 转换 intelligence 库异常为自定义异常
            raise convert_intelligence_error(e) from e

    async def generate_with_context(
        self,
        prompt: str,
        context_messages: list[dict],
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        **kwargs,
    ) -> str:
        """
        带上下文的生成

        Args:
            prompt: 当前用户输入
            context_messages: 上下文消息列表
                [{"role": "user/assistant", "content": "..."}]
            system: 系统提示词

        Returns:
            生成的文本

        Raises:
            NovelError: 转换后的自定义异常
        """
        messages = []
        if system:
            messages.append(Message.system(system))

        # 添加上下文消息
        for msg in context_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(Message.user(content))
            elif role == "assistant":
                messages.append(Message.assistant(content))

        # 添加当前输入
        messages.append(Message.user(prompt))

        config = GenerateConfig(
            model=kwargs.get("model", self.model),
            temperature=temperature,
            max_tokens=max_tokens,
        )

        try:
            response = await generate_text(
                messages=messages,
                provider=self._provider,
                **config.to_dict()
                if hasattr(config, "to_dict")
                else {"model": config.model},
            )
            return response.text  # type: ignore[no-any-return]
        except Exception as e:
            # 转换 intelligence 库异常为自定义异常
            raise convert_intelligence_error(e) from e

    async def stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        **kwargs,
    ):
        """
        流式生成

        Yields:
            增量文本
        """
        messages = []
        if system:
            messages.append(Message.system(system))
        messages.append(Message.user(prompt))

        config = GenerateConfig(
            model=kwargs.get("model", self.model),
            temperature=temperature,
            max_tokens=max_tokens,
        )

        async for chunk in stream_text(
            messages=messages,
            provider=self._provider,
            **config.to_dict()
            if hasattr(config, "to_dict")
            else {"model": config.model},
        ):
            yield chunk.delta

    def get_raw_provider(self):
        """获取底层 provider 实例（用于 superficial-thinking）"""
        return self._provider


def create_provider(config: dict) -> LLMProvider:
    """
    从配置创建 LLM 提供者

    Args:
        config: 配置字典
            {
                "type": "deepseek",
                "api_key": "sk-...",
                "base_url": "...",  # 可选
                "model": "deepseek-chat"
            }

    Returns:
        LLMProvider 实例
    """
    return LLMProvider(
        provider_type=config.get("type", "deepseek"),
        api_key=config.get("api_key", ""),
        base_url=config.get("base_url", ""),
        model=config.get("model", ""),
    )
