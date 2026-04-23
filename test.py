from backend.app.langgraph_framework.trip_nodes import refiner_node
from backend.app.langgraph_framework.trip_nodes import TripGraphState
from backend.app.models.schemas import TripPlan

# 模拟一个最简单的 plan（你可以用真实planner生成的）
mock_plan = {
    "city": "上海",
    "start_date": "2025-05-01",
    "end_date": "2025-05-02",
    "days": [
        {
            "date": "2025-05-01",
            "day_index": 0,
            "description": "第一天",
            "transportation": "地铁",
            "accommodation": "酒店",
            "hotel": {
                "name": "测试酒店",
                "address": "上海",
                "location": {"longitude": 121.47, "latitude": 31.23},
                "price_range": "300-500",
                "rating": "4.5",
                "distance": "1km",
                "type": "经济型",
                "estimated_cost": 400
            },
            "attractions": [
                {
                    "name": "外滩",
                    "address": "上海外滩",
                    "location": {"longitude": 121.49, "latitude": 31.24},
                    "visit_duration": 120,
                    "description": "景点",
                    "category": "景点",
                    "ticket_price": 0
                }
            ],
            "meals": []
        }
    ],
    "weather_info": [],
    "overall_suggestions": "",
    "budget": {
        "total_attractions": 0,
        "total_hotels": 400,
        "total_meals": 0,
        "total_transportation": 0,
        "total": 400
    }
}

state: TripGraphState = {
    "plan": TripPlan(**mock_plan),
    "user_feedback": "第一天太单调了，加一个景点"
}

result = refiner_node(state)

print("===== 原计划 =====")
print(mock_plan)

print("===== 修改后 =====")
print(result["plan"])