"""LangGraph Graph 构建：定义边/入口并编译可运行应用。"""

from langgraph.graph import END, StateGraph

from .trip_nodes import plan_trip_node
from .trip_state import TripGraphState


def build_trip_graph():
    """
    构建并编译一个最简旅行规划 Graph。
    Graph 结构：
      entry -> plan_trip -> END
    """

    workflow = StateGraph(TripGraphState)

    workflow.add_node("plan_trip", plan_trip_node)
    workflow.set_entry_point("plan_trip")
    workflow.add_edge("plan_trip", END)

    return workflow.compile()

