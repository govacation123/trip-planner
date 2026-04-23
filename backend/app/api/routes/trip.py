"""旅行规划API路由"""

from fastapi import APIRouter, HTTPException
from ...models.schemas import (
    TripRequest,
    TripPlanResponse,
    TripRefineRequest,
    ErrorResponse
)
from ...langgraph_framework.trip_graph import build_trip_graph

router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post(
    "/plan",
    response_model=TripPlanResponse,
    summary="生成旅行计划",
    description="根据用户输入的旅行需求,生成详细的旅行计划"
)
async def plan_trip(request: TripRequest):
    """
    生成旅行计划

    Args:
        request: 旅行请求参数

    Returns:
        旅行计划响应
    """
    try:
        print(f"\n{'='*60}")
        print(f"📥 收到旅行规划请求:")
        print(f"   城市: {request.city}")
        print(f"   日期: {request.start_date} - {request.end_date}")
        print(f"   天数: {request.travel_days}")
        print(f"{'='*60}\n")

        # 实例化LangGraph
        print("🔄 初始化LangGraph...")
        graph = build_trip_graph()

        # 运行LangGraph
        print("🚀 开始运行LangGraph生成旅行计划...")
        result = await graph.ainvoke({"request": request})
        trip_plan = result.get("plan")

        # 检查是否有错误信息
        error_msg = result.get("error")
        if error_msg:
            print(f"⚠️  LangGraph执行遇到问题，使用备用计划: {error_msg}\n")
            return TripPlanResponse(
                success=False,
                message=f"旅行计划生成遇到问题，已返回备用计划（原因：{error_msg}）",
                data=trip_plan
            )

        print("✅ 旅行计划生成成功,准备返回响应\n")

        return TripPlanResponse(
            success=True,
            message="旅行计划生成成功",
            data=trip_plan
        )

    except Exception as e:
        print(f"❌ 生成旅行计划失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"生成旅行计划失败: {str(e)}"
        )


@router.post(
    "/refine",
    response_model=TripPlanResponse,
    summary="优化/修改旅行计划",
    description="根据用户反馈对已有旅行计划进行修改"
)
async def refine_trip(request: TripRefineRequest):
    """
    优化/修改旅行计划

    Args:
        request: 包含原计划和用户修改意见的请求

    Returns:
        修改后的旅行计划响应
    """
    try:
        print(f"\n{'='*60}")
        print(f"📥 收到旅行计划优化请求:")
        print(f"   原计划城市: {request.plan.city}")
        print(f"   用户反馈: {request.user_feedback}")
        print(f"{'='*60}\n")

        # 构建状态：只传 plan 和 user_feedback
        state = {
            "plan": request.plan,
            "user_feedback": request.user_feedback
        }

        # 实例化LangGraph
        print("🔄 初始化LangGraph...")
        graph = build_trip_graph()

        # 运行LangGraph
        print("🚀 开始运行LangGraph优化旅行计划...")
        result = await graph.ainvoke(state)
        updated_plan = result.get("plan")

        # 检查是否有错误信息
        error_msg = result.get("error")
        if error_msg:
            print(f"⚠️  计划优化遇到问题: {error_msg}\n")
            return TripPlanResponse(
                success=False,
                message=f"计划优化遇到问题（原因：{error_msg}）",
                data=updated_plan
            )

        print("✅ 旅行计划优化成功,准备返回响应\n")

        return TripPlanResponse(
            success=True,
            message="旅行计划优化成功",
            data=updated_plan
        )

    except Exception as e:
        print(f"❌ 优化旅行计划失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"优化旅行计划失败: {str(e)}"
        )


@router.get(
    "/health",
    summary="健康检查",
    description="检查旅行规划服务是否正常"
)
async def health_check():
    """健康检查"""
    try:
        # 检查LangGraph是否可用
        graph = build_trip_graph()

        return {
            "status": "healthy",
            "service": "trip-planner",
            "graph_status": "initialized",
            "features": ["langgraph", "trip-planning"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"服务不可用: {str(e)}"
        )

