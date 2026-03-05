# Novel Generator

AI 驱动的小说生成系统，基于多 Agent 协作架构。

## 特性

- **多 Agent 协作**：Designer（架构设计）、Writer（章节写作）、Auditor（内容审计）、Polisher（文字润色）
- **知识库记忆**：自动维护角色设定、世界观、情节线索的一致性
- **断点续传**：支持保存进度、中断恢复、中途修改
- **灵活配置**：支持 OpenAI、DeepSeek、Anthropic 等多种 LLM

## 安装

```bash
pip install dawn-shuttle-novel
```

## 快速开始

### 1. 配置 API

```bash
novel config --api-key YOUR_API_KEY --base-url https://api.openai.com/v1 --model gpt-4
```

或使用环境变量：

```bash
export NOVEL_API_KEY=your_api_key
export NOVEL_BASE_URL=https://api.openai.com/v1
export NOVEL_MODEL=gpt-4
```

### 2. 创建小说

```bash
novel create "我的小说" -p "一部关于...的小说" -c 20 -w 3000 --design
```

### 3. 撰写章节

```bash
# 写第一章
novel write "我的小说" -c 1

# 写全部剩余章节
novel write "我的小说" --all
```

### 4. 查看与导出

```bash
# 查看状态
novel status "我的小说"

# 列出章节
novel list "我的小说"

# 导出
novel export "我的小说" -o output.txt
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `novel config` | 配置 API |
| `novel create` | 创建新小说 |
| `novel design` | 执行架构设计 |
| `novel write` | 撰写章节 |
| `novel list` | 列出小说/章节 |
| `novel status` | 查看状态 |
| `novel export` | 导出小说 |

## 项目结构

```
src/
├── cli.py           # 命令行入口
├── generator.py     # 生成器主类
├── agent/           # Agent 模块
│   ├── designer.py  # 架构设计
│   ├── writer.py    # 章节写作
│   ├── auditor.py   # 内容审计
│   └── polisher.py  # 文字润色
├── core/            # 核心数据结构
│   ├── graph/       # 图结构（角色/事件/地点关系）
│   ├── timeline.py  # 时间轴
│   ├── character.py # 角色卡
│   ├── map.py       # 世界地图
│   └── state.py     # 状态管理
└── llm/             # LLM 接口
    ├── provider.py  # 提供者封装
    └── knowledge.py # 知识库
```

## 依赖

- [dawn_shuttle_intelligence](https://github.com/dawn-shuttle/intelligence) - LLM 调用库
- [dawn_shuttle_superficial_thinking](https://github.com/dawn-shuttle/superficial-thinking) - 知识库/记忆系统

## License

MIT