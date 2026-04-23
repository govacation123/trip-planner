"""LangGraph State 定义：用于旅行规划流程。"""

from typing import Any, Optional, TypedDict

from ..models.schemas import TripPlan, TripRequest


class TripGraphState(TypedDict, total=False):
    """Graph 运行时的共享状态。"""

    # 输入：用户请求
    request: TripRequest

    # 中间结果：各智能体的处理结果
    intermediate_result: dict[str, Any]

    # 输出：旅行计划结果
    plan: Optional[TripPlan]

    # 错误信息（失败时节点仍会尝试生成回退 plan）
    error: Optional[str]

