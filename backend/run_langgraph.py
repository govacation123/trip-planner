"""LangGraph 示例入口：演示 State / 节点 / Graph 编译与 invoke 运行。"""
import sys
import asyncio
from app.langgraph_framework.trip_graph import build_trip_graph
from app.models.schemas import TripRequest

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
def main() -> None:
    graph = build_trip_graph()

    # 你可以在这里替换为真实参数。

    request = TripRequest(
        city="北京",
        start_date="2025-06-01",
        end_date="2025-06-03",
        travel_days=3,
        transportation="公共交通",
        accommodation="经济型酒店",
        preferences=["历史文化", "美食"],
        free_text_input="希望多安排一些博物馆",
    )

    result = graph.invoke({"request": request})
    plan = result.get("plan")

    print("LangGraph执行完成")
    print("是否生成 plan:", plan is not None)
    if result.get("error"):
        print("节点 error（可能来自 LLM/外部工具失败，仍可使用回退 plan）:", result["error"])

    if plan is None:
        return

    print("城市:", plan.city)
    print("日期:", plan.start_date, "->", plan.end_date)
    print("天数:", len(plan.days))
    if plan.days:
        print("第1天景点:", [a.name for a in plan.days[0].attractions])


if __name__ == "__main__":
    main()

