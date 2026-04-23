# 智能旅行助手 🌍✈️

基于 LangGraph + LangChain 构建的智能旅行规划助手，集成高德地图 Web API，提供个性化的旅行计划生成与多轮优化功能。

## ✨ 功能特点

- 🤖 **AI驱动的旅行规划**: 基于 LangGraph 框架，多节点并行执行（天气、酒店、景点），智能生成详细的多日旅程
- 🗺️ **高德地图集成**: 直接调用高德地图 REST API，支持景点搜索、路线规划、天气查询
- 🔄 **多轮优化**: 支持用户反馈修改计划，AI 对原计划进行最小化修改而非重写
- 💬 **实时对话**: 右侧聊天面板可直接输入修改意见，无需刷新页面
- 🎨 **现代化前端**: Vue3 + TypeScript + Vite，响应式设计，流畅的用户体验
- 📱 **完整功能**: 包含住宿、交通、餐饮和景点游览时间推荐

## 🏗️ 技术栈

### 后端
- **框架**: LangGraph + LangChain
- **API**: FastAPI
- **LLM**: 通义千问（通过 DashScope API）
- **地图**: 高德地图 Web REST API

### 前端
- **框架**: Vue 3 + TypeScript
- **构建工具**: Vite
- **UI组件库**: Ant Design Vue
- **地图服务**: 高德地图 JavaScript API
- **HTTP客户端**: Axios

## 📁 项目结构

```
trip-planner/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/               # FastAPI路由
│   │   │   ├── main.py
│   │   │   └── routes/
│   │   │       ├── trip.py    # 旅行规划API（含/refine）
│   │   │       ├── map.py     # 地图服务API
│   │   │       └── poi.py     # POI搜索API
│   │   ├── langgraph_framework/  # LangGraph核心
│   │   │   ├── trip_graph.py  # 图结构定义
│   │   │   ├── trip_nodes.py  # 节点定义（weather/hotel/attraction/planner/refiner）
│   │   │   └── trip_state.py  # 状态定义
│   │   ├── services/          # 服务层
│   │   │   └── amap_service.py  # 高德地图API封装
│   │   ├── models/            # 数据模型
│   │   │   └── schemas.py
│   │   └── config.py          # 配置管理
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── views/
│   │   │   ├── Home.vue       # 首页（旅行表单）
│   │   │   └── Result.vue     # 结果页（左侧计划+右侧聊天面板）
│   │   └── types/
│   │       └── index.ts       # TypeScript类型定义
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## 🚀 快速开始

### 前提条件

- Python 3.10+
- Node.js 16+
- 高德地图 API 密钥（Web 服务 API）
- 通义千问 API 密钥（DashScope）

### 后端安装

1. 进入后端目录
```bash
cd backend
```

2. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 API 密钥
```

5. 启动后端服务
```bash
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端安装

1. 进入前端目录
```bash
cd frontend
```

2. 安装依赖
```bash
npm install
```

3. 配置环境变量
```bash
cp .env.example .env
# 填入高德地图 Web API Key 和 Web 端 JS API Key
```

4. 启动开发服务器
```bash
npm run dev
```

5. 打开浏览器访问 `http://localhost:5173`

## 📝 使用指南

### 首次生成旅行计划

1. 在首页填写旅行信息：
   - 目的地城市
   - 旅行日期和天数
   - 交通方式偏好
   - 住宿偏好
   - 旅行风格标签

2. 点击「生成旅行计划」按钮

3. 系统将：
   - **并行**调用天气、酒店、景点三个节点
   - 汇总数据后由 Planner 生成完整行程
   - 展示每日详细计划、景点地图、天气预报

### 多轮优化修改

1. 在结果页面右侧的聊天面板输入修改意见，例如：
   - 「第二天行程太紧凑了，请调整轻松一些」
   - 「增加更多美食推荐」
   - 「把第三天的博物馆换成自然景观」

2. 点击发送按钮

3. 系统调用 `/api/trip/refine` 接口：
   - LLM 读取原计划，根据反馈进行**最小修改**
   - 返回更新后的计划（不重写全部行程）
   - 左侧视图自动更新

4. 可多次对话，逐步优化

## 🔧 核心实现

### LangGraph 图结构

```
用户输入
    ↓
START → 条件路由（根据 user_feedback）
    ├─ 有反馈 → refiner_node → END
    └─ 无反馈 → [weather_agent || hotel_agent || attraction_agent] 并行
                    ↓
               planner_agent → END
```

### 高德地图 API 封装

直接调用高德 REST API，无需 MCP 工具：

```python
# 搜索 POI
GET https://restapi.amap.com/v3/place/text?keywords=故宫&city=北京&key=YOUR_KEY

# 查询天气
GET https://restapi.amap.com/v3/weather/weatherinfo?city=北京&extensions=all&key=YOUR_KEY

# 地理编码
GET https://restapi.amap.com/v3/geocode/geo?address=北京市朝阳区&key=YOUR_KEY
```

## 📄 API 文档

启动后端服务后，访问 `http://localhost:8000/docs` 查看完整的 API 文档。

主要端点：
- `POST /api/trip/plan` - 生成旅行计划
- `POST /api/trip/refine` - 优化/修改旅行计划
- `GET /api/map/poi` - 搜索 POI
- `GET /api/map/weather` - 查询天气
- `POST /api/map/route` - 规划路线

## 📜 开源协议

CC BY-NC-SA 4.0

## 🙏 致谢

- [LangGraph](https://langchain-ai.github.io/langgraph/) - 多智能体编排框架
- [LangChain](https://www.langchain.com/) - LLM 应用开发框架
- [高德地图开放平台](https://lbs.amap.com/) - 地图服务
- [通义千问](https://tongyi.aliyun.com/) - 大语言模型

---

**智能旅行助手** - 让旅行计划变得简单而智能 🌈