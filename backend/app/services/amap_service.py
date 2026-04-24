"""高德地图服务封装 - 直接调用高德API"""

import json
import re
from typing import List, Dict, Any, Optional
import requests

from ..config import get_settings
from ..models.schemas import Location, POIInfo, WeatherInfo

# 全局服务实例
_amap_service = None

# 高德地图API基础URL
AMAP_BASE_URL = "https://restapi.amap.com/v3"


class AmapService:
    """高德地图服务封装类"""

    def __init__(self):
        """初始化服务"""
        settings = get_settings()
        self.api_key = settings.amap_api_key
        if not self.api_key:
            raise ValueError("高德地图API Key未配置，请在.env文件中设置AMAP_API_KEY")
        print(f"✅ 高德地图服务初始化成功")

    def _request(self, endpoint: str, params: dict) -> dict:
        """
        发起高德API请求

        Args:
            endpoint: API端点（如 "/weather/weatherinfo"）
            params: 请求参数（不包含key）

        Returns:
            API响应字典
        """
        params["key"] = self.api_key
        url = f"{AMAP_BASE_URL}{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ 高德API请求失败: {str(e)}")
            return {"status": "0", "info": str(e)}

    def search_poi(self, keywords: str, city: str, citylimit: bool = True) -> List[POIInfo]:
        """
        搜索POI

        Args:
            keywords: 搜索关键词
            city: 城市
            citylimit: 是否限制在城市范围内

        Returns:
            POI信息列表
        """
        try:
            params = {
                "keywords": keywords,
                "city": city,
                "citylimit": "true" if citylimit else "false",
                "output": "json",
                "offset": 10,
                "page": 1,
                "types": ""  # 不限制类型，搜索全部POI
            }
            result = self._request("/place/text", params)

            if result.get("status") != "1":
                print(f"❌ POI搜索失败: {result.get('info', '未知错误')}")
                return []

            pois = result.get("pois", [])
            poi_list = []
            for poi in pois:
                # 解析经纬度
                location_str = poi.get("location", "")
                longitude, latitude = 0.0, 0.0
                if location_str:
                    try:
                        lng, lat = location_str.split(",")
                        longitude, latitude = float(lng), float(lat)
                    except ValueError:
                        pass

                poi_info = POIInfo(
                    id=poi.get("id", ""),
                    name=poi.get("name", ""),
                    type=poi.get("type", ""),
                    address=poi.get("address", ""),
                    location=Location(longitude=longitude, latitude=latitude),
                    tel=poi.get("tel")
                )
                poi_list.append(poi_info)

            print(f"✅ POI搜索成功，找到 {len(poi_list)} 个结果")
            return poi_list

        except Exception as e:
            print(f"❌ POI搜索异常: {str(e)}")
            return []

    def get_weather(self, city: str) -> List[WeatherInfo]:
        """
        查询天气。

        策略：优先通过地理编码获取 adcode，再查询预报天气；
              如 adcode 获取失败则直接用城市名查实时天气。
        """
        try:
            # Step 1: 尝试通过地理编码获取 adcode（更精准）
            adcode = None
            try:
                geocode_result = self._request("/geocode/geo", {"address": city, "output": "json"})
                if geocode_result.get("status") == "1" and geocode_result.get("geocodes"):
                    adcode = geocode_result["geocodes"][0].get("adcode")
                    print(f"✅ 地理编码成功，{city} → adcode: {adcode}")
            except Exception as e:
                print(f"⚠️ 地理编码失败，使用城市名查询: {e}")

            # Step 2: 查询天气（优先用 adcode）
            if adcode:
                params = {
                    "city": adcode,
                    "extensions": "all",
                    "output": "json"
                }
                result = self._request("/weather/weatherinfo", params)

                if result.get("status") != "1":
                    print(f"⚠️ adcode 查询天气失败，尝试城市名 fallback: {result.get('info')}")
                    result = None

            if not adcode or result is None:
                # fallback: 直接用城市名查实时天气
                params = {
                    "city": city,
                    "extensions": "base",
                    "output": "json"
                }
                result = self._request("/weather/weatherinfo", params)

            if result.get("status") != "1":
                print(f"❌ 天气查询失败: {result.get('info', '未知错误')}")
                return []

            weather_list = []
            forecasts = result.get("forecasts", [])

            if forecasts:
                for fc in forecasts[0].get("casts", []):
                    weather_info = WeatherInfo(
                        date=fc.get("date", ""),
                        day_weather=fc.get("dayweather", ""),
                        night_weather=fc.get("nightweather", ""),
                        day_temp=int(fc.get("daytemp", 0)),
                        night_temp=int(fc.get("nighttemp", 0)),
                        wind_direction=fc.get("daywind", ""),
                        wind_power=fc.get("daypower", "")
                    )
                    weather_list.append(weather_info)
            else:
                live = result.get("lives", [])
                for live_data in live:
                    weather_info = WeatherInfo(
                        date=live_data.get("reporttime", "")[:10],
                        day_weather=live_data.get("weather", ""),
                        night_weather=live_data.get("weather", ""),
                        day_temp=int(live_data.get("temperature", 0)),
                        night_temp=int(live_data.get("temperature", 0)),
                        wind_direction=live_data.get("winddirection", ""),
                        wind_power=live_data.get("windpower", "")
                    )
                    weather_list.append(weather_info)

            print(f"✅ 天气查询成功，返回 {len(weather_list)} 天的天气")
            return weather_list

        except Exception as e:
            print(f"❌ 天气查询异常: {str(e)}")
            return []

    def plan_route(
        self,
        origin_address: str,
        destination_address: str,
        origin_city: Optional[str] = None,
        destination_city: Optional[str] = None,
        route_type: str = "walking"
    ) -> Dict[str, Any]:
        """
        规划路线

        Args:
            origin_address: 起点地址
            destination_address: 终点地址
            origin_city: 起点城市
            destination_city: 终点城市
            route_type: 路线类型 (walking/driving/transit)

        Returns:
            路线信息
        """
        try:
            # 根据路线类型选择API端点
            endpoint_map = {
                "walking": "/direction/walking",
                "driving": "/direction/driving",
                "transit": "/transit/integrated"
            }
            endpoint = endpoint_map.get(route_type, "/direction/walking")

            params = {
                "origin": origin_address,
                "destination": destination_address,
                "output": "json"
            }

            if origin_city:
                params["city"] = origin_city

            result = self._request(endpoint, params)

            if result.get("status") != "1":
                print(f"❌ 路线规划失败: {result.get('info', '未知错误')}")
                return {}

            # 解析路线结果
            route_info = {"type": route_type, "steps": []}

            if route_type == "walking":
                paths = result.get("paths", [])
                if paths:
                    path = paths[0]
                    route_info["distance"] = path.get("distance", "")
                    route_info["duration"] = path.get("duration", "")
                    for step in path.get("steps", []):
                        route_info["steps"].append({
                            "instruction": step.get("instruction", ""),
                            "distance": step.get("distance", ""),
                            "duration": step.get("duration", "")
                        })
            elif route_type == "driving":
                paths = result.get("routes", [])
                if paths:
                    route = paths[0]
                    route_info["distance"] = route.get("distance", "")
                    route_info["duration"] = route.get("time", "")
                    for way in route.get("steps", []):
                        for nav in way.get("navigation", []):
                            route_info["steps"].append({
                                "instruction": nav.get("instruction", ""),
                                "distance": nav.get("distance", ""),
                                "action": nav.get("action", "")
                            })
            elif route_type == "transit":
                route_info["paths"] = result.get("route", {})

            print(f"✅ 路线规划成功")
            return route_info

        except Exception as e:
            print(f"❌ 路线规划异常: {str(e)}")
            return {}

    def geocode(self, address: str, city: Optional[str] = None) -> Optional[Location]:
        """
        地理编码(地址转坐标)

        Args:
            address: 地址
            city: 城市

        Returns:
            经纬度坐标
        """
        try:
            params = {"address": address}
            if city:
                params["city"] = city

            result = self._request("/geocode/geo", params)

            if result.get("status") != "1":
                print(f"❌ 地理编码失败: {result.get('info', '未知错误')}")
                return None

            geocodes = result.get("geocodes", [])
            if not geocodes:
                return None

            location_str = geocodes[0].get("location", "")
            if not location_str:
                return None

            try:
                lng, lat = location_str.split(",")
                return Location(longitude=float(lng), latitude=float(lat))
            except ValueError:
                return None

        except Exception as e:
            print(f"❌ 地理编码异常: {str(e)}")
            return None

    def get_poi_detail(self, poi_id: str) -> Dict[str, Any]:
        """
        获取POI详情

        Args:
            poi_id: POI ID

        Returns:
            POI详情信息
        """
        try:
            # 高德place/detail接口
            params = {"id": poi_id}
            result = self._request("/place/detail", params)

            if result.get("status") != "1":
                print(f"❌ 获取POI详情失败: {result.get('info', '未知错误')}")
                return {}

            # 解析location
            location_str = result.get("location", "")
            longitude, latitude = 0.0, 0.0
            if location_str:
                try:
                    lng, lat = location_str.split(",")
                    longitude, latitude = float(lng), float(lat)
                except ValueError:
                    pass

            detail = {
                "id": result.get("id", ""),
                "name": result.get("name", ""),
                "type": result.get("type", ""),
                "address": result.get("address", ""),
                "location": {"longitude": longitude, "latitude": latitude},
                "tel": result.get("tel", ""),
                "pcode": result.get("pcode", ""),
                "citycode": result.get("citycode", ""),
                "adcode": result.get("adcode", ""),
                "business_area": result.get("business_area", ""),
            }

            print(f"✅ 获取POI详情成功: {result.get('name', '')}")
            return detail

        except Exception as e:
            print(f"❌ 获取POI详情异常: {str(e)}")
            return {}


def get_amap_service() -> AmapService:
    """获取高德地图服务实例(单例模式)"""
    global _amap_service

    if _amap_service is None:
        _amap_service = AmapService()

    return _amap_service