"""LangGraph 节点定义：旅行规划节点与失败回退。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from hello_agents import SimpleAgent
from hello_agents.tools import MCPTool
from ..services.llm_service import get_llm
from ..models.schemas import (
    Attraction,
    DayPlan,
    Location,
    Meal,
    TripPlan,
    TripRequest,
)
from ..config import get_settings
from .trip_state import TripGraphState


def _build_fallback_plan(request: TripRequest) -> TripPlan:
    """
    生成一个不依赖 LLM/外部工具的"兜底"旅行计划。
    目的是让 LangGraph 示例在缺少 API Key 时也能跑通。
    """

    start_date = datetime.strptime(request.start_date, "%Y-%m-%d")

    days: list[DayPlan] = []
    for i in range(request.travel_days):
        current_date = start_date + timedelta(days=i)

        attractions: list[Attraction] = []
        for j in range(2):
            attractions.append(
                Attraction(
                    name=f"{request.city}景点{i + 1}-{j + 1}",
                    address=f"{request.city}市",
                    location=Location(
                        longitude=116.4 + i * 0.01 + j * 0.005,
                        latitude=39.9 + i * 0.01 + j * 0.005,
                    ),
                    visit_duration=120,
                    description="这是回退方案中的景点占位描述。",
                    category="景点",
                    ticket_price=0,
                )
            )

        meals: list[Meal] = [
            Meal(type="breakfast", name=f"第{i + 1}天早餐", description="当地早餐（回退方案）"),
            Meal(type="lunch", name=f"第{i + 1}天午餐", description="午餐推荐（回退方案）"),
            Meal(type="dinner", name=f"第{i + 1}天晚餐", description="晚餐推荐（回退方案）"),
        ]

        days.append(
            DayPlan(
                date=current_date.strftime("%Y-%m-%d"),
                day_index=i,
                description=f"第{i + 1}天行程（回退方案）",
                transportation=request.transportation,
                accommodation=request.accommodation,
                attractions=attractions,
                meals=meals,
            )
        )

    return TripPlan(
        city=request.city,
        start_date=request.start_date,
        end_date=request.end_date,
        days=days,
        weather_info=[],
        overall_suggestions=f"这是为您规划的{request.city}{request.travel_days}日游行程（回退方案），建议提前查看各景点的开放时间。",
    )


def weather_node(state: TripGraphState) -> dict[str, Any]:
    """
    节点：天气查询智能体
    """
    import json

    request = state.get("request")
    if request is None:
        raise ValueError("TripGraphState 缺少 request")

    try:
        # 初始化LLM和工具
        llm = get_llm()
        settings = get_settings()
        amap_tool = MCPTool(
            name="amap",
            description="高德地图服务",
            server_command=["uvx", "amap-mcp-server"],
            env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
            auto_expand=False
        )

        # 创建天气查询Agent
        from ..agents.trip_planner_agent import WEATHER_AGENT_PROMPT
        weather_agent = SimpleAgent(
            name="天气查询专家",
            llm=llm,
            system_prompt=WEATHER_AGENT_PROMPT
        )
        weather_agent.add_tool(amap_tool)

        # 预先获取工具列表
        tools_overview = amap_tool.run({"action": "list_tools"})
        if tools_overview:
            tools_overview = f"\n\n【amap 可用工具清单】\n{tools_overview}\n"
        else:
            tools_overview = "\n\n【amap 可用工具清单】\n（空）\n"

        # 查询天气
        weather_query = (
            f"请查询 {request.city} 在 {request.start_date} 到 {request.end_date} 的天气信息。"
            f"如果工具仅支持实时天气，也请返回实时天气并说明限制。"
        ) + tools_overview

        weather_response = weather_agent.run(weather_query)

        # 存储中间结果
        intermediate_result = state.get("intermediate_result", {})
        intermediate_result["weather_data"] = weather_response

        return {"intermediate_result": intermediate_result, "error": None}
    except Exception as e:
        # 即使失败也存储空的天气数据，并传递错误信息
        intermediate_result = state.get("intermediate_result", {})
        intermediate_result["weather_data"] = "无法获取天气数据"

        return {"intermediate_result": intermediate_result, "error": f"{type(e).__name__}: {e}"}


def hotel_node(state: TripGraphState) -> dict[str, Any]:
    """
    节点：酒店推荐智能体
    """
    import json

    request = state.get("request")
    if request is None:
        raise ValueError("TripGraphState 缺少 request")

    try:
        # 初始化LLM和工具
        llm = get_llm()
        settings = get_settings()
        amap_tool = MCPTool(
            name="amap",
            description="高德地图服务",
            server_command=["uvx", "amap-mcp-server"],
            env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
            auto_expand=False
        )

        # 创建酒店推荐Agent
        from ..agents.trip_planner_agent import HOTEL_AGENT_PROMPT
        hotel_agent = SimpleAgent(
            name="酒店推荐专家",
            llm=llm,
            system_prompt=HOTEL_AGENT_PROMPT
        )
        hotel_agent.add_tool(amap_tool)

        # 预先获取工具列表
        tools_overview = amap_tool.run({"action": "list_tools"})
        if tools_overview:
            tools_overview = f"\n\n【amap 可用工具清单】\n{tools_overview}\n"
        else:
            tools_overview = "\n\n【amap 可用工具清单】\n（空）\n"

        # 搜索酒店
        hotel_query = (
            f"请搜索 {request.city} 的 {request.accommodation}（或相近类型）酒店，返回 5-8 个候选。"
            f"如果有多个商圈/区域可选，请优先市中心或主要景点集中区域。"
        ) + tools_overview

        hotel_response = hotel_agent.run(hotel_query)

        # 存储中间结果
        intermediate_result = state.get("intermediate_result", {})
        intermediate_result["hotel_data"] = hotel_response

        return {"intermediate_result": intermediate_result, "error": None}
    except Exception as e:
        # 即使失败也存储空的酒店数据，并传递错误信息
        intermediate_result = state.get("intermediate_result", {})
        intermediate_result["hotel_data"] = "无法获取酒店数据"

        return {"intermediate_result": intermediate_result, "error": f"{type(e).__name__}: {e}"}


def attraction_node(state: TripGraphState) -> dict[str, Any]:
    """
    节点：景点搜索智能体
    """
    import json

    request = state.get("request")
    if request is None:
        raise ValueError("TripGraphState 缺少 request")

    try:
        # 初始化LLM和工具
        llm = get_llm()
        settings = get_settings()
        amap_tool = MCPTool(
            name="amap",
            description="高德地图服务",
            server_command=["uvx", "amap-mcp-server"],
            env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
            auto_expand=False
        )

        # 创建景点搜索Agent
        from ..agents.trip_planner_agent import ATTRACTION_AGENT_PROMPT
        attraction_agent = SimpleAgent(
            name="景点搜索专家",
            llm=llm,
            system_prompt=ATTRACTION_AGENT_PROMPT
        )
        attraction_agent.add_tool(amap_tool)

        # 预先获取工具列表
        tools_overview = amap_tool.run({"action": "list_tools"})
        if tools_overview:
            tools_overview = f"\n\n【amap 可用工具清单】\n{tools_overview}\n"
        else:
            tools_overview = "\n\n【amap 可用工具清单】\n（空）\n"

        # 构建景点查询
        prefs = ", ".join(request.preferences) if request.preferences else "无"
        attraction_query = (
            f"请根据偏好（{prefs}）为 {request.city} 搜索适合的景点/POI，"
            f"覆盖多个类别（如博物馆/历史街区/公园/地标等），返回 8-12 个候选。\n"
            f"你必须先用 amap 工具 list_tools 找到可用的 tool_name，然后再用 call_tool 调用对应工具完成搜索。"
        ) + tools_overview

        attraction_response = attraction_agent.run(attraction_query)

        # 存储中间结果
        intermediate_result = state.get("intermediate_result", {})
        intermediate_result["attraction_data"] = attraction_response

        return {"intermediate_result": intermediate_result, "error": None}
    except Exception as e:
        # 即使失败也存储空的景点数据，并传递错误信息
        intermediate_result = state.get("intermediate_result", {})
        intermediate_result["attraction_data"] = "无法获取景点数据"

        return {"intermediate_result": intermediate_result, "error": f"{type(e).__name__}: {e}"}


def planner_node(state: TripGraphState) -> dict[str, Any]:
    """
    节点：行程规划智能体
    """
    import json

    request = state.get("request")
    if request is None:
        raise ValueError("TripGraphState 缺少 request")

    try:
        # 初始化LLM（此节点不需要外部工具，只负责整合信息）
        llm = get_llm()

        # 创建行程规划Agent
        from ..agents.trip_planner_agent import PLANNER_AGENT_PROMPT
        planner_agent = SimpleAgent(
            name="行程规划专家",
            llm=llm,
            system_prompt=PLANNER_AGENT_PROMPT
        )

        # 获取中间结果
        intermediate_result = state.get("intermediate_result", {})
        attraction_data = intermediate_result.get("attraction_data", "无数据")
        weather_data = intermediate_result.get("weather_data", "无数据")
        hotel_data = intermediate_result.get("hotel_data", "无数据")

        # 构建规划查询
        query = f"""请根据以下信息生成{request.city}的{request.travel_days}天旅行计划:

**基本信息:**
- 城市: {request.city}
- 日期: {request.start_date} 至 {request.end_date}
- 天数: {request.travel_days}天
- 交通方式: {request.transportation}
- 住宿: {request.accommodation}
- 偏好: {', '.join(request.preferences) if request.preferences else '无'}

**景点信息:**
{attraction_data}

**天气信息:**
{weather_data}

**酒店信息:**
{hotel_data}

**要求:**
1. 每天安排2-3个景点
2. 每天必须包含早中晚三餐
3. 每天推荐一个具体的酒店(从酒店信息中选择)
3. 考虑景点之间的距离和交通方式
4. 返回完整的JSON格式数据
5. 景点的经纬度坐标要真实准确
"""
        if request.free_text_input:
            query += f"\n**额外要求:** {request.free_text_input}"

        # 生成最终计划
        planner_response = planner_agent.run(query)

        # 解析响应
        try:
            # 尝试从响应中提取JSON
            if "```json" in planner_response:
                json_start = planner_response.find("```json") + 7
                json_end = planner_response.find("```", json_start)
                json_str = planner_response[json_start:json_end].strip()
            elif "```" in planner_response:
                json_start = planner_response.find("```") + 3
                json_end = planner_response.find("```", json_start)
                json_str = planner_response[json_start:json_end].strip()
            elif "{" in planner_response and "}" in planner_response:
                # 直接查找JSON对象
                json_start = planner_response.find("{")
                json_end = planner_response.rfind("}") + 1
                json_str = planner_response[json_start:json_end]
            else:
                raise ValueError("响应中未找到JSON数据")

            # 解析JSON
            data = json.loads(json_str)

            # 转换为TripPlan对象
            trip_plan = TripPlan(**data)

            return {"plan": trip_plan, "error": None}
        except Exception as parse_error:
            print(f"⚠️  解析响应失败: {str(parse_error)}")
            print(f"   将使用备用方案生成计划")
            plan = _build_fallback_plan(request)
            return {"plan": plan, "error": f"解析响应失败: {str(parse_error)}"}

    except Exception as e:
        plan = _build_fallback_plan(request)
        return {"plan": plan, "error": f"{type(e).__name__}: {e}"}

