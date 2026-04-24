"""旅行规划API路由"""

from typing import Any
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
        print(f"   Session ID: {request.session_id or '无'}")
        print(f"{'='*60}\n")

        # 从 memory_service 获取用户长期偏好
        user_profile = {}
        if request.session_id:
            from ...services.memory_service import get_user_profile
            user_profile = get_user_profile(request.session_id)
            print(f"📋 加载用户偏好: {user_profile}")

        # 构建状态
        state: dict[str, Any] = {
            "plan": request.plan,
            "user_feedback": request.user_feedback,
            "user_id": request.session_id,
            "user_profile": user_profile,
            "history": [],  # 新会话从空历史开始
            "scenario": request.scenario  # 用户表单原始选择的场景，优先于推断值
        }

        # 实例化LangGraph
        print("🔄 初始化LangGraph...")
        graph = build_trip_graph()

        # 运行LangGraph
        print("🚀 开始运行LangGraph优化旅行计划...")
        result = await graph.ainvoke(state)
        updated_plan = result.get("plan")

        # 获取更新后的 user_profile 和 history
        updated_profile = result.get("user_profile", user_profile)
        updated_history = result.get("history", [])

        # 如果有 user_id，保存更新后的偏好
        if request.session_id and updated_profile:
            from ...services.memory_service import save_user_profile
            save_user_profile(request.session_id, updated_profile)
            print(f"💾 已保存用户偏好: {updated_profile}")

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

