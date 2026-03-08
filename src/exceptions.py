"""小说生成器异常定义

定义所有自定义异常类型，用于精确的错误处理和用户友好的错误消息。

异常层级：
    NovelError (基类)
    ├── APIError (API 相关错误)
    │   ├── AuthenticationError (认证失败 401)
    │   ├── PermissionError (权限不足 403)
    │   ├── RateLimitError (速率限制 429)
    │   ├── QuotaExceededError (配额超限)
    │   ├── ModelNotFoundError (模型不存在)
    │   └── APIServerError (服务器错误 500/502/503)
    ├── NetworkError (网络相关错误)
    │   ├── ConnectionError (连接失败)
    │   └── TimeoutError (请求超时)
    ├── ConfigError (配置相关错误)
    │   └── MissingAPIKeyError (API Key 未配置)
    ├── ValidationError (输入验证错误)
    │   └── InvalidChapterError (章节号无效)
    └── StateError (状态相关错误)
        ├── NovelNotFoundError (小说不存在)
        └── ChapterNotFoundError (章节不存在)
"""


class NovelError(Exception):
    """小说生成器基础异常"""

    def __init__(self, message: str, hint: str | None = None):
        """
        初始化异常

        Args:
            message: 错误消息
            hint: 用户提示（可选）
        """
        self.message = message
        self.hint = hint
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


# ============================================================
# API 相关错误
# ============================================================


class APIError(NovelError):
    """API 调用相关错误基类"""

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        status_code: int | None = None,
    ):
        self.status_code = status_code
        super().__init__(message, hint)


class AuthenticationError(APIError):
    """认证失败 (401) - API Key 无效或已过期"""

    def __init__(self, message: str = "API Key 无效或已过期"):
        super().__init__(
            message,
            hint="请使用 'novel config --api-key YOUR_KEY' 更新密钥",
            status_code=401,
        )


class APIPermissionError(APIError):
    """权限不足 (403)"""

    def __init__(self, message: str = "无权限访问该资源"):
        super().__init__(
            message,
            hint="请检查 API Key 是否有相应权限",
            status_code=403,
        )


class RateLimitError(APIError):
    """请求频率超限 (429)"""

    def __init__(self, message: str = "API 请求频率超限"):
        super().__init__(
            message,
            hint="请等待几分钟后重试",
            status_code=429,
        )


class QuotaExceededError(APIError):
    """配额超限"""

    def __init__(self, message: str = "API 配额不足"):
        super().__init__(
            message,
            hint="请检查账户余额或升级套餐",
            status_code=None,
        )


class ModelNotFoundError(APIError):
    """模型不存在"""

    def __init__(self, model: str = ""):
        message = f"模型 '{model}' 不存在" if model else "模型不存在"
        super().__init__(
            message,
            hint="请使用 'novel config --model MODEL_NAME' 设置正确的模型",
            status_code=None,
        )


class APIServerError(APIError):
    """API 服务器错误 (500/502/503)"""

    def __init__(self, message: str = "API 服务暂时不可用"):
        super().__init__(
            message,
            hint="请稍后重试",
            status_code=None,
        )


class ContentFilterError(APIError):
    """内容过滤触发"""

    def __init__(self, message: str = "内容触发安全过滤"):
        super().__init__(
            message,
            hint="请修改提示词，避免敏感内容",
            status_code=None,
        )


class InvalidRequestError(APIError):
    """无效请求 (400)"""

    def __init__(self, message: str = "请求参数无效"):
        super().__init__(
            message,
            hint="请检查输入参数是否正确",
            status_code=400,
        )


# ============================================================
# 网络相关错误
# ============================================================


class NetworkError(NovelError):
    """网络相关错误基类"""

    pass


class ConnectionFailedError(NetworkError):
    """连接失败"""

    def __init__(self, message: str = "网络连接失败"):
        super().__init__(
            message,
            hint="请检查网络连接或稍后重试",
        )


class RequestTimeoutError(NetworkError):
    """请求超时"""

    def __init__(self, message: str = "请求超时"):
        super().__init__(
            message,
            hint="请检查网络连接或稍后重试",
        )


# ============================================================
# 配置相关错误
# ============================================================


class ConfigError(NovelError):
    """配置相关错误基类"""

    pass


class MissingAPIKeyError(ConfigError):
    """API Key 未配置"""

    def __init__(self):
        super().__init__(
            "未配置 API Key",
            hint="请使用 'novel config --api-key YOUR_KEY' 设置密钥",
        )


class DependencyError(ConfigError):
    """依赖缺失"""

    def __init__(self, dependency: str = ""):
        message = f"缺少依赖: {dependency}" if dependency else "缺少依赖"
        super().__init__(
            message,
            hint=f"请运行: pip install {dependency}",
        )


# ============================================================
# 验证相关错误
# ============================================================


class ValidationError(NovelError):
    """输入验证错误基类"""

    pass


class InvalidChapterError(ValidationError):
    """章节号无效"""

    def __init__(self, chapter: int, total: int):
        super().__init__(
            f"章节号 {chapter} 超出范围 (总共 {total} 章)",
            hint="请使用有效的章节号",
        )


class InvalidTitleError(ValidationError):
    """标题无效"""

    def __init__(self, title: str = ""):
        super().__init__(
            f"小说标题 '{title}' 无效" if title else "小说标题无效",
            hint="标题不能为空，且不能包含特殊字符",
        )


# ============================================================
# 状态相关错误
# ============================================================


class StateError(NovelError):
    """状态相关错误基类"""

    pass


class NovelNotFoundError(StateError):
    """小说不存在"""

    def __init__(self, title: str):
        super().__init__(
            f"未找到小说 '{title}'",
            hint="请使用 'novel list' 查看所有小说",
        )


class ChapterNotFoundError(StateError):
    """章节不存在"""

    def __init__(self, title: str, chapter: int):
        super().__init__(
            f"小说 '{title}' 第 {chapter} 章不存在",
            hint="请使用 'novel list TITLE' 查看已完成章节",
        )


class DesignNotFoundError(StateError):
    """设计不存在"""

    def __init__(self, title: str):
        super().__init__(
            f"小说 '{title}' 尚未进行设计",
            hint=f"请使用 'novel design {title}' 进行设计",
        )


# ============================================================
# 文件系统错误
# ============================================================


class FileSystemError(NovelError):
    """文件系统错误基类"""

    pass


class FileNotFoundError(FileSystemError):
    """文件未找到"""

    def __init__(self, path: str):
        super().__init__(
            f"文件未找到: {path}",
            hint="请检查文件路径是否正确",
        )


class FileWriteError(FileSystemError):
    """文件写入失败"""

    def __init__(self, path: str, reason: str = ""):
        message = f"写入文件失败: {path}"
        if reason:
            message += f" ({reason})"
        super().__init__(
            message,
            hint="请检查磁盘空间和文件权限",
        )


# ============================================================
# 异常转换工具函数
# ============================================================


def convert_intelligence_error(e: Exception) -> NovelError:
    """
    将 intelligence 库的异常转换为自定义异常

    Args:
        e: 原始异常

    Returns:
        转换后的自定义异常
    """
    error_type = type(e).__name__
    error_str = str(e)

    # 映射 intelligence 库的异常类型
    error_map = {
        "AuthenticationError": AuthenticationError,
        "RateLimitError": RateLimitError,
        "QuotaExceededError": QuotaExceededError,
        "ModelNotFoundError": ModelNotFoundError,
        "InternalServerError": APIServerError,
        "TimeoutError": RequestTimeoutError,
        "ConnectionError": ConnectionFailedError,
        "ContentFilterError": ContentFilterError,
        "InvalidRequestError": InvalidRequestError,
        "ProviderNotAvailableError": APIServerError,
        "ConfigurationError": ConfigError,
        "ResponseParseError": APIError,
    }

    if error_type in error_map:
        exc_class = error_map[error_type]
        return exc_class(error_str)  # type: ignore[no-any-return, call-arg]

    # 尝试从错误消息推断
    error_lower = error_str.lower()

    if "401" in error_str or "unauthorized" in error_lower:
        return AuthenticationError()
    if "403" in error_str or "forbidden" in error_lower:
        return APIPermissionError()
    if "429" in error_str or "rate limit" in error_lower:
        return RateLimitError()
    if "500" in error_str or "502" in error_str or "503" in error_str:
        return APIServerError()
    if (
        "insufficient" in error_lower
        or "quota" in error_lower
        or "balance" in error_lower
    ):
        return QuotaExceededError()
    if "timeout" in error_lower:
        return RequestTimeoutError()
    if "connection" in error_lower or "network" in error_lower:
        return ConnectionFailedError()

    # 未知错误，返回通用 API 错误
    return APIError(error_str)


def get_error_code(error: Exception) -> int:
    """
    获取错误的退出码

    Args:
        error: 异常对象

    Returns:
        退出码
    """
    import asyncio

    # 用户中断
    if isinstance(error, KeyboardInterrupt):
        return 130
    if isinstance(error, asyncio.CancelledError):
        return 130

    # 自定义异常的错误码映射
    code_map = {
        AuthenticationError: 5,
        APIPermissionError: 5,
        RateLimitError: 6,
        QuotaExceededError: 8,
        APIServerError: 7,
        ConnectionFailedError: 1,
        RequestTimeoutError: 1,
        MissingAPIKeyError: 5,
        DependencyError: 10,
        ValidationError: 9,
        StateError: 2,
        FileSystemError: 3,
        ConfigError: 4,
    }

    for error_class, code in code_map.items():
        if isinstance(error, error_class):
            return code

    # 其他错误
    return 1
