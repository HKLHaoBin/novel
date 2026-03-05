"""LLM 提供者适配层 - 封装 intelligence 库"""

# intelligence 库的导入
try:
    from dawn_shuttle.dawn_shuttle_intelligence import (
        Message,
        GenerateConfig,
        generate_text,
        stream_text,
        OpenAIProvider,
        AnthropicProvider,
        GoogleProvider,
        DeepSeekProvider,
        MoonshotProvider,
        OpenAICompatibleProvider,
    )
    INTELLIGENCE_AVAILABLE = True
except ImportError:
    INTELLIGENCE_AVAILABLE = False


class LLMProvider:
    """LLM 提供者封装"""
    
    def __init__(
        self,
        provider_type: str = "deepseek",
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        **kwargs
    ):
        """
        初始化 LLM 提供者
        
        Args:
            provider_type: 提供者类型 (openai/anthropic/google/deepseek/moonshot/compatible)
            api_key: API 密钥
            base_url: 自定义 API 地址（可选）
            model: 默认模型
        """
        if not INTELLIGENCE_AVAILABLE:
            raise ImportError("intelligence 库未安装，请确保 dawn_shuttle_intelligence 可用")
        
        self.provider_type = provider_type
        self.model = model
        self._provider = self._create_provider(provider_type, api_key, base_url, **kwargs)
    
    def _create_provider(self, provider_type: str, api_key: str, base_url: str, **kwargs):
        """创建底层 provider"""
        providers = {
            "openai": lambda: OpenAIProvider(api_key=api_key, base_url=base_url or None, **kwargs),
            "anthropic": lambda: AnthropicProvider(api_key=api_key, **kwargs),
            "google": lambda: GoogleProvider(api_key=api_key, **kwargs),
            "deepseek": lambda: DeepSeekProvider(api_key=api_key, **kwargs),
            "moonshot": lambda: MoonshotProvider(api_key=api_key, **kwargs),
            "compatible": lambda: OpenAICompatibleProvider(api_key=api_key, base_url=base_url, **kwargs),
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
        **kwargs
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
        """
        messages = []
        if system:
            messages.append(Message.system(system))
        messages.append(Message.user(prompt))
        
        config = GenerateConfig(
            model=kwargs.get("model", self.model),
            temperature=temperature,
            max_tokens=max_tokens,
            **{k: v for k, v in kwargs.items() if k not in ["model"]}
        )
        
        response = await generate_text(
            messages=messages,
            provider=self._provider,
            **config.to_dict() if hasattr(config, 'to_dict') else {"model": config.model}
        )
        
        return response.text
    
    async def generate_with_context(
        self,
        prompt: str,
        context_messages: list[dict],
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        **kwargs
    ) -> str:
        """
        带上下文的生成
        
        Args:
            prompt: 当前用户输入
            context_messages: 上下文消息列表 [{"role": "user/assistant", "content": "..."}]
            system: 系统提示词
            
        Returns:
            生成的文本
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
        
        response = await generate_text(
            messages=messages,
            provider=self._provider,
            **config.to_dict() if hasattr(config, 'to_dict') else {"model": config.model}
        )
        
        return response.text
    
    async def stream(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4000,
        **kwargs
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
            **config.to_dict() if hasattr(config, 'to_dict') else {"model": config.model}
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
