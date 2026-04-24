"""用户记忆服务 - SQLite持久化 + 场景化长期记忆"""

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# 数据库路径（项目根目录下）
DB_PATH = Path(__file__).parent.parent.parent / "memory.db"

# Session 过期时间（30天）
SESSION_EXPIRE_DAYS = 30

# 线程锁（保证 SQLite 并发安全）
_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（线程安全）"""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    """初始化数据库表"""
    with _lock:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_memory (
                user_id TEXT PRIMARY KEY,
                profile TEXT,
                updated_at TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()


# 启动时初始化表
_init_db()


def get_user_profile(user_id: str) -> dict:
    """
    获取用户长期记忆（包含所有场景的记忆）。

    - 如果 session 超过 30 天未更新，自动删除并返回空 dict
    - 如果 user_id 不存在，返回空 dict

    Args:
        user_id: 用户标识（session_id）

    Returns:
        用户 profile 字典，格式：{"scenarios": {"场景名": {...}, ...}}
    """
    if not user_id:
        return {}

    with _lock:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT profile, updated_at FROM user_memory WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {}

        profile_json = row["profile"]
        updated_at_str = row["updated_at"]

        # 解析 updated_at
        try:
            updated_at = datetime.fromisoformat(updated_at_str)
        except (ValueError, TypeError):
            return {}

        # 检查是否过期（超过 30 天）
        expire_time = datetime.now() - timedelta(days=SESSION_EXPIRE_DAYS)
        if updated_at < expire_time:
            # 删除过期数据
            delete_user_profile(user_id)
            return {}

        # 解析 profile
        if profile_json:
            try:
                return json.loads(profile_json)
            except json.JSONDecodeError:
                return {}

        return {}


def get_scenario_memory(user_id: str, scenario: str) -> dict:
    """
    精准召回：仅获取指定场景的记忆。

    Args:
        user_id: 用户标识
        scenario: 场景名称（如"商务出差"、"亲子度假"）

    Returns:
        该场景的记忆字典，无数据时返回空 dict
    """
    if not user_id or not scenario:
        return {}

    full_profile = get_user_profile(user_id)
    scenarios = full_profile.get("scenarios", {})
    return scenarios.get(scenario, {})


def save_user_profile(user_id: str, profile: dict):
    """
    保存用户长期记忆（完整覆盖）。

    Args:
        user_id: 用户标识
        profile: 用户 profile 字典（按场景隔离的结构）
    """
    if not user_id:
        return

    profile_json = json.dumps(profile, ensure_ascii=False)

    with _lock:
        conn = _get_conn()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO user_memory (user_id, profile, updated_at)
            VALUES (?, ?, ?)
            """,
            (user_id, profile_json, datetime.now().isoformat())
        )

        conn.commit()
        conn.close()


def save_scenario_memory(user_id: str, scenario: str, memory: dict):
    """
    保存指定场景的记忆（增量合并到该场景下）。

    Args:
        user_id: 用户标识
        scenario: 场景名称
        memory: 该场景的偏好记忆
    """
    if not user_id or not scenario:
        return

    # 获取现有完整 profile
    full_profile = get_user_profile(user_id)

    # 确保 scenarios 结构存在
    if "scenarios" not in full_profile:
        full_profile["scenarios"] = {}

    # 合并到指定场景
    if scenario in full_profile["scenarios"]:
        full_profile["scenarios"][scenario] = merge_scenario_memory(
            full_profile["scenarios"][scenario],
            memory
        )
    else:
        full_profile["scenarios"][scenario] = memory

    save_user_profile(user_id, full_profile)


def merge_scenario_memory(old: dict, new: dict) -> dict:
    """
    合并同一场景下的新旧记忆。

    规则：
    - 新值优先
    - list 去重合并
    - None 不覆盖旧值

    Args:
        old: 旧记忆
        new: 新记忆

    Returns:
        合并后的记忆
    """
    result = dict(old)

    for key, value in new.items():
        if value is None:
            continue

        if key in result:
            old_value = result[key]
            if isinstance(old_value, list) and isinstance(value, list):
                # list 去重合并
                seen = set()
                merged_list = []
                for item in old_value + value:
                    item_key = str(item)
                    if item_key not in seen:
                        seen.add(item_key)
                        merged_list.append(item)
                result[key] = merged_list
            else:
                result[key] = value
        else:
            result[key] = value

    return result


def merge_user_profile(old: dict, new: dict, scenario: Optional[str] = None) -> dict:
    """
    合并旧 profile 和新数据。

    如果指定了 scenario，新数据合并到 old["scenarios"][scenario] 下。

    规则：
    - 新值优先
    - list 去重合并
    - None 不覆盖旧值

    Args:
        old: 旧 profile
        new: 新数据
        scenario: 场景名称（可选）

    Returns:
        合并后的 profile
    """
    if scenario:
        # 场景化模式：合并到指定场景下
        result = dict(old)
        if "scenarios" not in result:
            result["scenarios"] = {}
        if scenario not in result["scenarios"]:
            result["scenarios"][scenario] = {}
        result["scenarios"][scenario] = merge_scenario_memory(
            result["scenarios"][scenario],
            new
        )
        return result
    else:
        # 兼容模式：直接合并到顶层
        result = dict(old)
        for key, value in new.items():
            if value is None:
                continue
            if key in result:
                old_value = result[key]
                if isinstance(old_value, list) and isinstance(value, list):
                    seen = set()
                    merged_list = []
                    for item in old_value + value:
                        item_key = str(item)
                        if item_key not in seen:
                            seen.add(item_key)
                            merged_list.append(item)
                    result[key] = merged_list
                else:
                    result[key] = value
            else:
                result[key] = value
        return result


def update_user_profile(user_id: str, new_data: dict, scenario: Optional[str] = None):
    """
    更新用户长期记忆（增量合并）。

    Args:
        user_id: 用户标识
        new_data: 新数据（部分字段）
        scenario: 场景名称（可选）
    """
    if not user_id:
        return

    if scenario:
        save_scenario_memory(user_id, scenario, new_data)
    else:
        old_profile = get_user_profile(user_id)
        merged = merge_user_profile(old_profile, new_data)
        save_user_profile(user_id, merged)


def delete_user_profile(user_id: str):
    """
    删除用户记忆。

    Args:
        user_id: 用户标识
    """
    if not user_id:
        return

    with _lock:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_memory WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()


def cleanup_expired_sessions() -> int:
    """
    清理所有过期 session。

    Returns:
        删除的 session 数量
    """
    expire_time = datetime.now() - timedelta(days=SESSION_EXPIRE_DAYS)

    with _lock:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM user_memory WHERE updated_at < ?",
            (expire_time.isoformat(),)
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

    return deleted


from collections import Counter

def get_popular_scenario_preferences(scenario: str, top_k: int = 3) -> dict:
    """
    【群体智慧引擎】提取全网所有用户在该场景下最高频的 Top K 偏好。

    Args:
        scenario: 场景名称，如 "商务出差"
        top_k: 返回最高频的前几个偏好

    Returns:
        包含最高频偏好的字典，如 {"住宿": "离高铁近", "节奏": "紧凑"}
    """
    if not scenario:
        return {}

    with _lock:
        conn = _get_conn()
        cursor = conn.cursor()
        expire_time = datetime.now() - timedelta(days=SESSION_EXPIRE_DAYS)
        cursor.execute(
            "SELECT profile FROM user_memory WHERE updated_at >= ?",
            (expire_time.isoformat(),)
        )
        rows = cursor.fetchall()
        conn.close()

    preference_counter: Counter = Counter()

    for row in rows:
        if not row["profile"]:
            continue
        try:
            profile_data = json.loads(row["profile"])
            scenario_data = profile_data.get("scenarios", {}).get(scenario, {})

            for key, value in scenario_data.items():
                if isinstance(value, list):
                    for v in value:
                        preference_counter[(key, str(v))] = 1
                else:
                    preference_counter[(key, str(value))] += 1

        except json.JSONDecodeError:
            continue

    most_common = preference_counter.most_common(top_k)

    popular_prefs = {}
    for (key, val), _count in most_common:
        if key in popular_prefs:
            popular_prefs[key] = f"{popular_prefs[key]}, {val}"
        else:
            popular_prefs[key] = val

    return popular_prefs


def list_active_sessions() -> list:
    """
    列出所有未过期的 session。

    Returns:
        active user_id 列表
    """
    expire_time = datetime.now() - timedelta(days=SESSION_EXPIRE_DAYS)

    with _lock:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM user_memory WHERE updated_at >= ?",
            (expire_time.isoformat(),)
        )
        rows = cursor.fetchall()
        conn.close()

    return [row["user_id"] for row in rows]