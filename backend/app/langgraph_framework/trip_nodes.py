"""LangGraph 节点定义：旅行规划节点与失败回退。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..agents.trip_planner_agent import get_trip_planner_agent
from ..models.schemas import (
    Attraction,
    DayPlan,
    Location,
    Meal,
    TripPlan,
    TripRequest,
)
from .trip_state import TripGraphState


def _build_fallback_plan(request: TripRequest) -> TripPlan:
    """
    生成一个不依赖 LLM/外部工具的“兜底”旅行计划。
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


def plan_trip_node(state: TripGraphState) -> dict[str, Any]:
    """
    节点：根据 `state.request` 生成旅行计划，并写入 `state.plan`。
    如果项目的 HelloAgents/Llm 未配置或失败，则回退生成简易计划。
    """

    request = state.get("request")
    if request is None:
        raise ValueError("TripGraphState 缺少 request")

    try:
        planner = get_trip_planner_agent()
        plan = planner.plan_trip(request)
        return {"plan": plan, "error": None}
    except Exception as e:
        plan = _build_fallback_plan(request)
        return {"plan": plan, "error": f"{type(e).__name__}: {e}"}

