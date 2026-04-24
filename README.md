# 智能旅行助手 🌍✈️

基于 **LangGraph** + **LangChain** 构建的智能旅行规划助手，集成高德地图 REST API，提供个性化的旅行计划生成、多轮对话优化与场景化长期记忆功能。

---

## ✨ 功能特点

- 🤖 **AI 驱动的旅行规划**：基于 LangGraph 框架，多节点并行执行（天气、酒店、景点），智能生成详细的多日旅程
- 🗺️ **高德地图集成**：直接调用高德地图 REST API，支持景点搜索、路线规划、天气查询（基于 adcode 精准查询）
- 🔄 **多轮优化**：支持用户反馈修改计划，AI 对原计划进行**最小化精准修改**而非重写
- 💾 **三层记忆架构**：工作记忆（State）+ 短期记忆（history 滑动窗口）+ 场景化长期记忆（SQLite TTL）
- 🌐 **群体智慧**：聚合全网同类场景的 Top-K 大众偏好，作为规划时的辅助参考
- 💬 **实时对话**：右侧聊天面板可直接输入修改意见，无需刷新页面
- 🎯 **出行目的标签**：用户可在表单中选择场景（商务出差/亲子度假/情侣伴侣等），优先于 LLM 推断

---

## 🏗️ 技术栈

### 后端
- **框架**：LangGraph + LangChain
- **API**：FastAPI
- **LLM**：通义千问（通过 DashScope API）
- **地图**：高德地图 Web REST API
- **持久化**：SQLite（记忆服务，含 30 天 TTL 过期机制）

### 前端
- **框架**：Vue 3 + TypeScript + Vite
- **UI 组件库**：Ant Design Vue
- **地图服务**：高德地图 JavaScript API
- **HTTP 客户端**：Axios / Fetch

---

## 📁 项目结构

```
trip-planner/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── main.py
│   │   │   └── routes/
│   │   │       ├── trip.py          # /trip/plan, /trip/refine
│   │   │       ├── map.py           # 地图服务 API
│   │   │       └── poi.py           # POI 搜索 API
│   │   ├── langgraph_framework/
│   │   │   ├── trip_graph.py       # 图结构定义 + 条件路由
│   │   │   ├── trip_nodes.py       # 节点定义 + MCP 工具注册 + 群体智慧
│   │   │   ├── trip_state.py       # TripGraphState 定义
│   │   │   └── trip_nodesv1.py     # 备份（废弃）
│   │   ├── services/
│   │   │   ├── amap_service.py     # 高德地图 API 封装
│   │   │   └── memory_service.py   # SQLite 记忆服务（含群体智慧）
│   │   ├── models/
│   │   │   └── schemas.py          # Pydantic 数据模型
│   │   └── config.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── Home.vue            # 首页（表单 + 出行目的标签选择器）
│   │   │   └── Result.vue          # 结果页（左侧行程 + 右侧 AI 对话侧边栏）
│   │   ├── services/api.ts
│   │   └── types/index.ts
│   ├── .env.example
│   ├── package.json
│   └── vite.config.ts
├── 技术架构文档.md
└── README.md
```

---

## 🔄 执行流程详解

### 2.1 首次生成（无 user_feedback）

```
用户提交表单（携带 scenario 出行目的标签）
    │
    ▼
POST /api/trip/plan
    │
    ▼
条件路由：user_feedback? ──no──► weather_agent ──► hotel_agent ──► attraction_agent
                              │                                        │
                              └────────── planner_node ────────────────┘
                                                              │
                                            intermediate_result + crowd_memory
                                                              │
                                            LLM 生成完整 JSON 行程
                                                              │
                                                       TripPlan 对象
                                                              │
                                                       返回前端展示
```

### 2.2 多轮优化（有 user_feedback）

```
用户发送修改意见
    │
    ▼
POST /api/trip/refine { plan, user_feedback, session_id, scenario }
    │
    ▼
从 SQLite 加载 user_profile（session_id 关联）
    │
    ▼
ainvoke(state) ──► refiner_node
    │
    ▼
优先使用表单原始 scenario（避免纯文本推断错误）
    │
    ▼
extract_user_profile() 推断场景 + 偏好
    │
    ▼
save_scenario_memory(user_id, scenario, preferences) 增量保存
    │
    ▼
get_scenario_memory(user_id, scenario) 精准召回
    │
    ▼
REMAER_PROMPT（含 user_feedback / relevant_memory）最小化修改
    │
    ▼
返回更新后的 plan，前端左侧视图自动刷新
```

---

## 🧠 三层记忆架构

### 设计原则

> **硬约束 > 软约束，永远不让记忆覆盖用户指令**

| 层级 | 存储介质 | 生命周期 | 作用 |
|------|---------|---------|------|
| **工作记忆** | LangGraph State | 单次对话 | 保障当前行程数据一致性 |
| **短期记忆** | `state.history: List[str]` | 滑动窗口 | 解决多轮对话指代消解 |
| **长期记忆** | SQLite (`user_memory` 表) | 30 天 TTL | 场景化画像持久化 + 群体智慧 |

### 场景化召回

```python
# 记忆按场景隔离存储
profile = {
    "scenarios": {
        "亲子度假": { "住宿": "民宿", "节奏偏好": "宽松" },
        "商务出差": { "住宿": "五星级", "预算": "1000+" }
    }
}
```

- **首次规划**：使用 `get_popular_scenario_preferences(scenario, top_k=3)` 获取群体智慧 Top 偏好
- **Refine 时**：优先使用用户在表单原始选择的 `scenario`，只读对应场景的记忆
- **场景推断**：仅在用户明确说"改成OO"时才由 LLM `with_structured_output(MemoryExtraction)` 推断

### 约束优先级

```
[硬约束-Highest]  用户当前输入的指令
[硬约束-WorkMem]  当前计划中的硬性参数（城市/天数/基础预算）
[软约束-Soft]     场景化召回的长期记忆（relevant_memory）
[辅助-Optional]    群体智慧 Top 偏好（crowd_memory）
```

---

## 🔧 MCP 轻量工具注册体系

```
LLM (bind_tools)
    │
    ▼
amap_search_tool  ──►  TOOLS_REGISTRY["amap_search_tool"]
                              │
                              ▼
                        execute_tool(name, args)
                              │
                              ▼
                        AmapService (高德 REST API)
```

工具注册表：`trip_nodes.py` 中的 `TOOLS_REGISTRY`，通过 `register_tool()` / `execute_tool()` 管理。

---

## 📝 使用指南

### 首次生成旅行计划

1. 在首页填写旅行信息（目的地、日期、交通、住宿）
2. **点选出行目的标签**（💼商务出差 / 👶亲子度假 等，可选但建议填写）
3. 选择旅行偏好标签（历史文化/自然风光/美食等）
4. 点击「生成旅行计划」

### 多轮优化修改

1. 在结果页面**右侧聊天面板**输入修改意见，如：
   - 「第二天行程太紧凑了，请调整轻松一些」
   - 「换成亲子友好的景点」
2. 点击发送，系统进行**最小化精准修改**
3. 可多次对话，逐步优化
4. 每次 refine 后，偏好会自动保存到对应场景的记忆中

---

## 🚀 快速开始

### 后端

```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY、AMAP_API_KEY

uvicorn app.api.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
cp .env.example .env
# 编辑 .env，填入 VITE_AMAP_WEB_JS_KEY（高德地图 Web JS API Key）

npm run dev
# 访问 http://localhost:5173
```

### 环境变量说明

**后端 `.env`**
```bash
# LLM 配置（通义千问 DashScope）
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_ID=qwen-plus

# 高德地图 REST API Key
AMAP_API_KEY=xxxxxxxxxxxxxxxxxxxx
```

**前端 `.env`**
```bash
# 高德地图 Web JS API Key（用于前端地图展示，与 REST API Key 不同）
VITE_AMAP_WEB_JS_KEY=xxxxxxxxxxxxxxxxxxxx
```

---

## 📄 API 文档

启动后端后访问 `http://localhost:8000/docs`（Swagger UI）。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/trip/plan` | POST | 生成旅行计划 |
| `/api/trip/refine` | POST | 优化/修改旅行计划 |
| `/api/trip/health` | GET | 健康检查 |
| `/api/map/poi` | GET | 搜索 POI |
| `/api/map/weather` | GET | 查询天气 |
| `/api/map/route` | POST | 规划路线 |

**`/trip/refine` 请求体**
```json
{
  "plan": { /* TripPlan 对象 */ },
  "user_feedback": "第二天行程太紧凑了",
  "session_id": "xxxxxxxx-xxxx-xxxx",
  "scenario": "亲子度假"
}
```

---

## 🙏 致谢

- [LangGraph](https://langchain-ai.github.io/langgraph/) — 多智能体编排框架
- [LangChain](https://www.langchain.com/) — LLM 应用开发框架
- [高德地图开放平台](https://lbs.amap.com/) — 地图服务
- [通义千问](https://tongyi.aliyun.com/) — 大语言模型
- [Ant Design Vue](https://antdv.com/) — UI 组件库

---

**智能旅行助手** — 让旅行计划变得简单而智能 🌈