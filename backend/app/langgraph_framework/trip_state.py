"""LangGraph State 定义：用于旅行规划流程。"""

from typing import Any, Optional, TypedDict, List

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

    # 用户当前输入的修改意见
    user_feedback: Optional[str]

    # 记录用户多轮反馈要求
    history: List[str]

    # 用户标识（前端传入的 session_id）
    user_id: Optional[str]

    # 长期记忆（用户偏好等）
    user_profile: Optional[dict]

    # 当前出游场景（如"亲子度假"、"商务出差"等）
    current_scenario: Optional[str]

    # 仅针对当前场景召回的长期记忆
    relevant_memory: Optional[dict]

    # 用户在表单原始选择的场景（Refine 时从请求中传入，优先于推断值）
    scenario: Optional[str]

