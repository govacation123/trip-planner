"""LangGraph Graph 构建：定义边/入口并编译可运行应用。"""

from langgraph.graph import END, StateGraph

from .trip_nodes import attraction_node, hotel_node, planner_node, weather_node, refiner_node
from .trip_state import TripGraphState


def _route_based_on_feedback(state: TripGraphState) -> str:
    """
    根据 state.user_feedback 决定路由：
    - 有 feedback → 走 refiner_node（优化已有计划）
    - 无 feedback → 走 weather_agent（首次生成）
    """
    if state.get("user_feedback"):
        return "refiner_node"
    else:
        return "weather_agent"


def build_trip_graph():
    """
    构建并编译一个旅行规划 Graph。

    Graph 结构（首次生成）：
      START → weather_agent → hotel_agent → attraction_agent → planner_agent → END

    Graph 结构（优化修改）：
      START → refiner_node → END
    """
    workflow = StateGraph(TripGraphState)

    # 注册所有节点
    workflow.add_node("weather_agent", weather_node)
    workflow.add_node("hotel_agent", hotel_node)
    workflow.add_node("attraction_agent", attraction_node)
    workflow.add_node("planner_agent", planner_node)
    workflow.add_node("refiner_node", refiner_node)

    # 条件路由：基于 user_feedback 从 START 决定入口
    # __start__ 是 LangGraph 内置的入口节点
    workflow.add_conditional_edges(
        "__start__",
        _route_based_on_feedback,
        {
            "refiner_node": "refiner_node",
            "weather_agent": "weather_agent",
        }
    )

    # refiner_node 完成后直接 END
    workflow.add_edge("refiner_node", END)

    # 首次生成链路：weather -> hotel -> attraction -> planner -> END
    workflow.add_edge("weather_agent", "hotel_agent")
    workflow.add_edge("hotel_agent", "attraction_agent")
    workflow.add_edge("attraction_agent", "planner_agent")
    workflow.add_edge("planner_agent", END)

    return workflow.compile()

