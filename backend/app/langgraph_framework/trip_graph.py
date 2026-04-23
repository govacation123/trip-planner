"""LangGraph Graph 构建：定义边/入口并编译可运行应用。"""

from langgraph.graph import END, StateGraph

from .trip_nodes import attraction_node, hotel_node, planner_node, weather_node
from .trip_state import TripGraphState


def build_trip_graph():
    """
    构建并编译一个旅行规划 Graph。
    Graph 结构：
      entry -> weather_agent -> hotel_agent -> attraction_agent -> planner_agent -> END
    """

    workflow = StateGraph(TripGraphState)

    # 招募 4 个真正的智能体节点
    workflow.add_node("weather_agent", weather_node)
    workflow.add_node("hotel_agent", hotel_node)
    workflow.add_node("attraction_agent", attraction_node)
    workflow.add_node("planner_agent", planner_node)

    # 定义工作流转（）
    workflow.set_entry_point("weather_agent")
    workflow.add_edge("weather_agent", "hotel_agent")
    workflow.add_edge("hotel_agent", "attraction_agent")
    workflow.add_edge("attraction_agent", "planner_agent")
    workflow.add_edge("planner_agent", END)

    return workflow.compile()

