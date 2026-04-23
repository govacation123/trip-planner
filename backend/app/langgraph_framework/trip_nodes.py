"""LangGraph 节点定义：旅行规划节点与失败回退。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, List

# 引入 LangChain 核心机制
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, BaseMessage
from langchain_core.tools import tool

from ..config import get_settings
from ..models.schemas import (
    Attraction,
    DayPlan,
    Location,
    Meal,
    TripPlan,
    TripRequest,
)
from .trip_state import TripGraphState


# ============ 动态加载大模型配置 (完美替代原 get_llm) ============
def _get_langchain_llm() -> ChatOpenAI:
    """
    动态从 .env 中读取配置，实例化标准的 LangChain LLM。
    绝对不硬编码 API Key，完美兼容你原本的配置中心。
    """
    settings = get_settings()

    # 从 settings 的属性中获取配置（优先从 .env 读取的环境变量）
    api_key = settings.api_key
    model_name = settings.llm_model
    base_url = settings.llm_base_url
    timeout = settings.timeout

    if not api_key:
        raise ValueError("无法从环境中找到 API Key，请检查 .env 文件中的 LLM_API_KEY")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        temperature=0.7,
        max_retries=2
    )


# ============ 专业 Agent提示词 ============
ATTRACTION_AGENT_PROMPT = """你是高级景点搜索专家。
你的任务是根据城市和用户偏好搜索合适的景点。
请务必调用系统提供的高德地图(amap)相关工具来获取真实数据，绝不要凭空捏造。
返回包含景点名称、地址、特点和大概位置的信息。"""

WEATHER_AGENT_PROMPT = """你是高级天气查询专家。
你的任务是查询指定城市的天气信息。
请调用系统提供的高德地图(amap)工具来查询天气，绝不要凭空捏造。
如果工具只支持实时天气，请说明这是实时天气。"""

HOTEL_AGENT_PROMPT = """你是高级酒店推荐专家。
你的任务是根据城市和用户住宿偏好推荐合适的酒店。
请调用系统提供的高德地图(amap)工具搜索真实的酒店数据。
优先返回 5-8 个候选酒店，包含名称、位置和特色。"""

PLANNER_AGENT_PROMPT = """你是首席行程规划专家。
你的任务是根据前面助手收集的景点、天气和酒店信息，生成详细的旅行计划。

请严格按照以下JSON格式返回旅行计划（不要输出除JSON以外的任何内容）:
```json
{
  "city": "城市名称",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "days": [
    {
      "date": "YYYY-MM-DD",
      "day_index": 0,
      "description": "第1天行程概述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {"longitude": 116.397128, "latitude": 39.916527},
        "price_range": "300-500元",
        "rating": "4.5",
        "distance": "距离景点2公里",
        "type": "经济型酒店",
        "estimated_cost": 400
      },
      "attractions": [
        {
          "name": "景点名称",
          "address": "详细地址",
          "location": {"longitude": 116.397128, "latitude": 39.916527},
          "visit_duration": 120,
          "description": "景点详细描述",
          "category": "景点类别",
          "ticket_price": 60
        }
      ],
      "meals": [
        {"type": "breakfast", "name": "早餐推荐", "description": "早餐描述", "estimated_cost": 30},
        {"type": "lunch", "name": "午餐推荐", "description": "午餐描述", "estimated_cost": 50},
        {"type": "dinner", "name": "晚餐推荐", "description": "晚餐描述", "estimated_cost": 80}
      ]
    }
  ],
  "weather_info": [
    {
      "date": "YYYY-MM-DD",
      "day_weather": "晴",
      "night_weather": "多云",
      "day_temp": 25,
      "night_temp": 15,
      "wind_direction": "南风",
      "wind_power": "1-3级"
    }
  ],
  "overall_suggestions": "总体建议",
  "budget": {
    "total_attractions": 180,
    "total_hotels": 1200,
    "total_meals": 480,
    "total_transportation": 200,
    "total": 2060
  }
}

注意: 温度必须是纯数字，每天2-3个景点，必须包含预算信息。
"""


# ============ LangChain 标准工具定义 ============

@tool
def amap_search_tool(query: str, city: str, search_type: str) -> str:
    """
    高德地图综合搜索工具。
    使用此工具获取真实的地理位置、景点、酒店或天气信息。

    参数:
    - query: 搜索的关键词（如 "外滩", "如家酒店", "天气"）
    - city: 目标城市名称（如 "上海"）
    - search_type: 搜索类型，可选值为 "poi" (查景点/酒店) 或 "weather" (查天气)
    """
    from ..services.amap_service import get_amap_service

    print(f"🔧 [Tool Execution] 正在调用高德工具搜索: {city} 的 {query} (类型: {search_type})...")

    try:
        amap_service = get_amap_service()

        if search_type == "weather":
            # 查询天气
            weather_list = amap_service.get_weather(city)
            if weather_list:
                result_parts = []
                for w in weather_list:
                    result_parts.append(
                        f"{w.date}: 白天{w.day_weather}, 夜间{w.night_weather}, "
                        f"气温 {w.day_temp}-{w.night_temp}°C, "
                        f"{w.wind_direction}{w.wind_power}"
                    )
                return "\n".join(result_parts) if result_parts else f"{city}天气查询无结果"
            return f"{city}天气查询无结果"
        else:
            # POI搜索（景点、酒店等）
            poi_list = amap_service.search_poi(query, city)
            if poi_list:
                result_parts = []
                for i, poi in enumerate(poi_list[:10], 1):  # 最多返回10个结果
                    result_parts.append(
                        f"{i}. {poi.name}，地址：{poi.address}，"
                        f"经纬度: {poi.location.longitude}, {poi.location.latitude}，"
                        f"类型: {poi.type}"
                    )
                return "\n".join(result_parts) if result_parts else f"{city} {query} 搜索无结果"
            return f"{city} {query} 搜索无结果"

    except Exception as e:
        print(f"❌ 高德工具调用失败: {str(e)}")
        return f"高德地图API调用失败: {str(e)}"


# ============ 工具调用循环封装 ============

def _run_agent_with_tools(system_prompt: str, user_query: str) -> str:
    # 这里改用标准的 LangChain LLM 实例化方法
    llm = _get_langchain_llm()
    llm_with_tools = llm.bind_tools([amap_search_tool])

    messages: List[BaseMessage] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_query)
    ]

    ai_msg = llm_with_tools.invoke(messages)
    messages.append(ai_msg)

    if hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
        for tool_call in ai_msg.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            if tool_name == "amap_search_tool":
                tool_result = amap_search_tool.invoke(tool_args)
            else:
                tool_result = f"Error: 找不到名为 {tool_name} 的工具"

            messages.append(ToolMessage(
                content=str(tool_result),
                tool_call_id=tool_call["id"]
            ))

        final_msg = llm_with_tools.invoke(messages)
        return final_msg.content

    return ai_msg.content


# ============ LangGraph 节点 ============

def weather_node(state: TripGraphState) -> dict[str, Any]:
    request = state.get("request")
    intermediate_result = state.get("intermediate_result", {})
    try:
        query = f"请查询 {request.city} 在 {request.start_date} 到 {request.end_date} 的天气信息。"
        result = _run_agent_with_tools(WEATHER_AGENT_PROMPT, query)
        intermediate_result["weather_data"] = result
        return {"intermediate_result": intermediate_result, "error": None}
    except Exception as e:
        intermediate_result["weather_data"] = "无法获取天气数据"
        return {"intermediate_result": intermediate_result, "error": str(e)}


def hotel_node(state: TripGraphState) -> dict[str, Any]:
    request = state.get("request")
    intermediate_result = state.get("intermediate_result", {})
    try:
        query = f"请搜索 {request.city} 的 {request.accommodation} 酒店，返回 5-8 个候选。"
        result = _run_agent_with_tools(HOTEL_AGENT_PROMPT, query)
        intermediate_result["hotel_data"] = result
        return {"intermediate_result": intermediate_result, "error": None}
    except Exception as e:
        intermediate_result["hotel_data"] = "无法获取酒店数据"
        return {"intermediate_result": intermediate_result, "error": str(e)}


def attraction_node(state: TripGraphState) -> dict[str, Any]:
    request = state.get("request")
    intermediate_result = state.get("intermediate_result", {})
    try:
        prefs = ", ".join(request.preferences) if request.preferences else "无"
        query = f"请根据偏好（{prefs}）为 {request.city} 搜索适合的景点/POI，返回 8-12 个候选。"
        result = _run_agent_with_tools(ATTRACTION_AGENT_PROMPT, query)
        intermediate_result["attraction_data"] = result
        return {"intermediate_result": intermediate_result, "error": None}
    except Exception as e:
        intermediate_result["attraction_data"] = "无法获取景点数据"
        return {"intermediate_result": intermediate_result, "error": str(e)}


def planner_node(state: TripGraphState) -> dict[str, Any]:
    request = state.get("request")
    try:
        # 使用标准的 LangChain LLM 实例
        llm = _get_langchain_llm()
        intermediate_result = state.get("intermediate_result", {})
        attractions = intermediate_result.get("attraction_data", "无数据")
        weather = intermediate_result.get("weather_data", "无数据")
        hotels = intermediate_result.get("hotel_data", "无数据")

        query = f"""
请基于以下信息规划行程:
城市: {request.city} ({request.start_date} 至 {request.end_date}, 共{request.travel_days}天)
交通: {request.transportation} | 住宿: {request.accommodation} | 偏好: {request.preferences}

景点数据: {attractions}
天气数据: {weather}
酒店数据: {hotels}
"""
        messages = [
            SystemMessage(content=PLANNER_AGENT_PROMPT),
            HumanMessage(content=query)
        ]

        response = llm.invoke(messages)
        planner_response = response.content

        if "```json" in planner_response:
            json_str = planner_response.split("```json")[1].split("```")[0].strip()
        elif "```" in planner_response:
            json_str = planner_response.split("```")[1].split("```")[0].strip()
        elif "{" in planner_response and "}" in planner_response:
            json_start = planner_response.find("{")
            json_end = planner_response.rfind("}") + 1
            json_str = planner_response[json_start:json_end]
        else:
            raise ValueError("未找到JSON结构")

        data = json.loads(json_str)
        return {"plan": TripPlan(**data), "error": None}

    except Exception as e:
        print(f"⚠️ 生成计划失败: {str(e)}")
        plan = _build_fallback_plan(request)
        return {"plan": plan, "error": f"Planner解析失败: {e}"}


# ============ Refiner Node（计划优化节点）============

REFINER_PROMPT = """你是高级旅行计划优化专家。
你的任务是根据用户的修改意见，对已有的旅行计划进行**最小范围的精准修改**。

**明确修改策略**：
- 用户反馈“太累/行程紧” → 减少对应天数的景点数量，增加单景点游玩时长。
- 用户反馈“预算高/太贵” → 替换为更便宜的住宿或餐饮，并重新计算预算。
- 用户反馈“不想去A景点” → 仅把A景点替换为同城其他景点。
- 用户反馈“第X天不好” → 仅修改第X天的数据，其余天数原封不动。

**强制规则**：
1. 【最小修改】绝对不允许重写整个计划！只准改动用户提到的相关部分。
2. 【格式一致】必须返回完整 JSON，且结构必须与原计划 100% 一致，不允许缺失或新增字段。
3. 【只吐JSON】只返回 JSON 数据，不要包含任何解释性文字。
4. 【交互反馈】请将你具体做了哪些修改（例如："已将第一天酒店更换为如家，节省了100元"），追加写进 JSON 的 `overall_suggestions` 字段末尾，以便前端展示给用户。

用户修改意见：{feedback}

现有旅行计划：
{plan_json}

请输出修改后的完整 JSON："""
def build_refiner_prompt(plan: dict, feedback: str) -> str:
    """
    构造 Refiner 的 Prompt。

    Args:
        plan: 当前旅行计划（dict 格式）
        feedback: 用户的修改意见

    Returns:
        构造好的 prompt 字符串
    """
    plan_json = json.dumps(plan, ensure_ascii=False, indent=2)
    return REFINER_PROMPT.format(feedback=feedback, plan_json=plan_json)


def refiner_node(state: TripGraphState) -> dict[str, Any]:
    """
    根据用户反馈对已有计划进行最小修改。

    输入：
    - state.plan：已有旅行计划
    - state.user_feedback：用户修改意见

    输出：
    - 更新后的 plan
    - error 信息（如有）
    """
    plan = state.get("plan")
    user_feedback = state.get("user_feedback")

    if not plan:
        return {"error": "refiner_node: 原始计划不存在"}

    if not user_feedback:
        return {"plan": plan, "error": None}

    try:
        llm = _get_langchain_llm()
        plan_dict = plan.model_dump()
        prompt = build_refiner_prompt(plan_dict, user_feedback)

        messages = [
            SystemMessage(content="你是一个严谨的旅行计划修改助手，只输出JSON，不输出其他内容。"),
            HumanMessage(content=prompt)
        ]

        response = llm.invoke(messages)
        response_content = response.content

        # 提取 JSON
        if "```json" in response_content:
            json_str = response_content.split("```json")[1].split("```")[0].strip()
        elif "```" in response_content:
            json_str = response_content.split("```")[1].split("```")[0].strip()
        elif "{" in response_content and "}" in response_content:
            json_start = response_content.find("{")
            json_end = response_content.rfind("}") + 1
            json_str = response_content[json_start:json_end]
        else:
            raise ValueError("未找到JSON结构")

        updated_data = json.loads(json_str)
        updated_plan = TripPlan(**updated_data)

        return {"plan": updated_plan, "error": None}

    except Exception as e:
        print(f"⚠️ 计划优化失败，回退原计划: {str(e)}")
        # JSON 解析失败时返回原计划，不抛异常
        return {"plan": plan, "error": f"Refiner解析失败: {e}"}


def _build_fallback_plan(request: TripRequest) -> TripPlan:
    """生成兜底旅行计划"""
    start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
    days: list[DayPlan] = []
    for i in range(request.travel_days):
        current_date = start_date + timedelta(days=i)
        days.append(DayPlan(
            date=current_date.strftime("%Y-%m-%d"),
            day_index=i,
            description=f"第{i + 1}天行程",
            transportation=request.transportation,
            accommodation=request.accommodation,
            attractions=[
                Attraction(
                    name=f"{request.city}占位景点",
                    address=f"{request.city}市",
                    location=Location(longitude=116.4, latitude=39.9),
                    visit_duration=120,
                    description="回退方案",
                    category="景点",
                    ticket_price=0
                )
            ],
            meals=[
                Meal(type="breakfast", name="早餐", description="默认早餐"),
                Meal(type="lunch", name="午餐", description="默认午餐"),
                Meal(type="dinner", name="晚餐", description="默认晚餐"),
            ],
        ))
    return TripPlan(
        city=request.city,
        start_date=request.start_date,
        end_date=request.end_date,
        days=days,
        weather_info=[],
        overall_suggestions="兜底方案。"
    )