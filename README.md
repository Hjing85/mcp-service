# ESPMCP —— Python MCP Server / Client 完整方案

基于 MCP 官方 Python SDK（`mcp` 包）实现，一套代码同时支持**国内外主流 Agent / 智能体**的连接。

## ✨ 可视化配置（v2 新增）

- **服务端管理后台**（`http://localhost:8000/admin`）：
  - 数据源网关：配置外部系统的公共查询语句 + JSON 参数白名单，查询结果经过滤后作为数据集返回给 Agent
  - 授权密钥：签发 `pk_` 前缀公共 Key（仅存哈希、创建时明文只显示一次），绑定可访问的数据源、可启停
  - 审计日志：记录每次数据查询
- **客户端控制台**（`python -m mcp_client.run_webapp` 后访问 `http://127.0.0.1:8500/`）：
  - 按系统分别配置各家模型的 API Key / Base URL / 模型名，持久化到 `config/client_providers.json`
  - 配置 Server 地址、传输方式（SSE / Streamable HTTP）、公共 Key 后测试连接、列出工具
  - Web 对话界面，展示每轮工具调用与结果
- **传输方式**：服务端默认 **SSE**（`http://host:8000/sse`），同时支持 `streamable-http` 与 `stdio`

## 架构

```
┌─────────────────────────────── Agent 侧 ────────────────────────────────┐
│  国际: OpenAI GPT / Claude / Gemini(兼容模式)                            │
│  国内: 通义千问 / DeepSeek / Kimi / 智谱GLM / 豆包 / 混元 / MiniMax / 文心  │
│  平台: Dify / Coze(扣子) / n8n / Cherry Studio 等（直接以 MCP Client 连接）│
└────────────────────────────────┬───────────────────────────────────────┘
                                 │  ①  SDK 直连（本仓库 mcp_client + 适配层）
                                 │  ②  平台原生 MCP 接入（填 Server URL 即可）
                    ┌────────────▼────────────┐
                    │   MCP Server (FastMCP)  │
                    │  streamable-http / stdio │
                    │  calculator weather ...  │
                    └─────────────────────────┘
```

## 目录结构

```
ESPMCP/
├── requirements.txt
├── .env.example              # API Key 模板（复制为 .env）
├── mcp_server/               # ===== MCP Server =====
│   ├── server.py             #   FastMCP 构建
│   ├── run_server.py         #   启动入口（stdio / streamable-http）
│   └── tools/                #   工具目录（新增工具只需加文件）
│   └──config/providers.yaml  # Agent/LLM 提供方注册表
├── mcp_client/               # ===== MCP Client =====
│   ├── client.py             #   连接/工具发现/多轮 Agent 循环
│   ├── run_client.py         #   CLI（交互 REPL 与单条问答）
│   └── adapters/             #   Agent 适配层
│       ├── openai_compatible.py   # 一个适配器覆盖国内外所有 OpenAI 兼容厂商
│       ├── anthropic_adapter.py   # Claude
│       └── registry.py            # 从 providers.yaml 创建适配器
└── examples/ask_once.py      # 编程调用示例
```

## 快速开始

### 方式 A：全可视化操作（推荐）

```powershell
pip install -r requirements.txt

# 终端 1：启动 MCP Server（SSE 模式 + 管理后台）
python -m mcp_server.run_server
# 浏览器打开 http://localhost:8000/admin 配置数据源、签发公共 Key

# 终端 2：启动客户端控制台
python -m mcp_client.run_webapp
# 浏览器打开 http://127.0.0.1:8500/ 配置模型 Key、填入 Server 地址与公共 Key，即可对话
```

### 方式 B：命令行

```powershell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置密钥（只需填你用到的厂商）
Copy-Item .env.example .env   # 然后编辑 .env

# 3. 启动 MCP Server（默认 SSE，端口 8000）
python -m mcp_server.run_server

# 4. 另开一个终端，用国内 Agent 连接
python -m mcp_client.run_client --provider qwen --server-url http://localhost:8000/sse --verbose
```

## 支持的连接方式

### 1. 本方案自带 MCP Client（代码接入）

```bash
python -m mcp_client.run_client --provider deepseek --server-url http://localhost:8000/mcp --ask "北京天气如何？"
python -m mcp_client.run_client --provider claude  --server-url http://localhost:8000/mcp
python -m mcp_client.run_client --provider qwen    --stdio "python -m mcp_server.run_server --transport stdio"
```

`providers.yaml` 中已预置：`openai / claude / deepseek / qwen / kimi / glm / doubao / hunyuan / minimax / ernie`。
任何 OpenAI 兼容厂商，在 `providers.yaml` 追加一段配置即可，**无需写代码**。

### 2. 平台原生 MCP 接入（零代码）

Dify、Coze（扣子）、n8n、Cherry Studio、Cursor、Cline、Claude Desktop 等平台现已原生支持 MCP Client，
直接把 Server 地址填进它们的 MCP 工具配置：

| 平台 | 接入方式 | 地址 |
|---|---|---|
| Dify | 工具 → MCP (SSE/HTTP) | `http://<host>:8000/sse` |
| Coze 扣子 | 插件 → MCP 扩展 | `http://<host>:8000/sse` |
| Cherry Studio / n8n | MCP 设置 | `http://<host>:8000/sse` |
| Claude Desktop / Cursor / Cline | mcpServers 配置（stdio） | 见下 |

Claude Desktop / Cursor 的 `mcpServers` 配置：

```json
{
  "mcpServers": {
    "espmcp": {
      "command": "python",
      "args": ["-m", "mcp_server.run_server", "--transport", "stdio"]
    }
  }
}
```

### 3. 编程方式

见 `examples/ask_once.py`：

```python
adapter = create_adapter("glm")
client = MCPAgentClient(adapter, system_prompt="...")
await client.connect(server_url="http://localhost:8000/mcp")
result = await client.chat([], "帮我算一下 (1024+2048)*3，并查北京天气")
```

## 新增自定义工具

在 `mcp_server/tools/` 新建文件（如 `search.py`），然后到 `tools/__init__.py` 注册：

```python
def register(mcp):
    @mcp.tool()
    async def web_search(query: str) -> str:
        """联网搜索并返回摘要。"""
        ...
```

## 数据网关与授权（服务端）

1. 打开 `http://localhost:8000/admin` → **数据源** → 添加：
   - `sqlite` 类型：DSN 填数据库文件路径，公共查询语句用命名占位符，如
     `SELECT id,city,amount,status FROM orders WHERE status = :status LIMIT :limit`
   - `http` 类型：DSN 填外部 API 基础地址，查询语句用 `{param}` 占位符，如 `/orders?status={status}`
   - 配置参数白名单 `{"status":"str","limit":"int"}`（不在白名单内的参数会被拒绝，防注入）
2. **授权密钥** → 绑定该密钥可访问的数据源 → 签发，明文 `pk_...` 只显示一次
3. 客户端携带密钥连接后，Agent 即可调用 `list_data_sources` / `query_data` 工具：
   - HTTP/SSE 客户端：连接时通过 `Authorization: Bearer pk_...` 请求头
   - stdio 客户端：调用 `query_data` 时传 `api_key` 参数
4. 每次查询均记入审计日志；未配置任何密钥时服务器处于开放模式（仅建议本地调试使用）

## 生产部署建议

- **鉴权**：公网部署时在 Nginx/Caddy 反向代理层加 HTTPS；MCP 数据访问用服务端签发的公共 Key（`/admin` 管理）。
- **HTTPS**：远程平台（Dify/Coze）接入要求公网 HTTPS，建议 `https://mcp.example.com/mcp`。
- **Docker**：`uvicorn` 已包含在依赖中，FastMCP 底层基于 Starlette/ASGI，可容器化部署。
- **密钥安全**：API Key 全部走环境变量（`.env`），不要提交到仓库。
