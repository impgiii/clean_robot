"""通过 Open-Meteo 地理编码和天气接口查询当前室外温湿度。"""
import math

import httpx


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def _place_name(place):
    parts = [place.get("name"), place.get("admin1"), place.get("country")]
    return "，".join(dict.fromkeys(part for part in parts if part))


def _normalized_name(name):
    return name.strip().removesuffix("市").casefold()


def _get_json(client, url, params):
    response = client.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("天气服务返回无效数据")
    return data


def _query_weather(client, city, region, country_code):
    city = city.strip().removesuffix("市")
    region = region.strip()
    country_code = country_code.strip().upper()
    if len(city) < 2:
        return "请提供完整的城市名称；必要时补充省份或国家。"
    if country_code and (len(country_code) != 2 or not country_code.isascii() or not country_code.isalpha()):
        return "国家代码应为两个英文字母，例如 CN；无法确定时请留空并补充地区。"

    params = {"name": f"{city}, {region}" if region else city,
              "count": 20, "language": "zh", "format": "json"}
    if country_code:
        params["countryCode"] = country_code
    places = _get_json(client, GEOCODING_URL, params).get("results", [])
    if not isinstance(places, list):
        raise ValueError("无效地区列表")
    places = [p for p in places if isinstance(p, dict) and isinstance(p.get("name"), str)
              and "latitude" in p and "longitude" in p]
    if country_code:
        places = [p for p in places if p.get("country_code") == country_code]
    if not places:
        return (f"没有找到城市“{city}”。请核对名称，或提供省份、国家、城市英文名。"
                "未取得天气数据，不能据此推测温湿度。")

    # 优先完整名称，其次选择城市级行政中心，避免把同名村庄当作城市。
    exact = [p for p in places if _normalized_name(p["name"]) == _normalized_name(city)]
    places = exact or places
    cities = [p for p in places if p.get("feature_code") in {"PPLC", "PPLA", "PPLA2"}]
    places = cities or places
    places = list({(p["latitude"], p["longitude"]): p for p in places}.values())
    if len(places) != 1:
        candidates = "；".join(_place_name(p) for p in places[:5])
        return (f"找到了多个可能的城市：{candidates}。"
                "请向用户确认省份或国家后再查询，不要自行选取。")

    place = places[0]
    latitude, longitude = float(place["latitude"]), float(place["longitude"])
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("无效坐标")
    weather = _get_json(client, WEATHER_URL, {
        "latitude": latitude, "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m",
        "temperature_unit": "celsius", "timezone": "auto", "forecast_days": 1,
    })
    current = weather["current"]
    temperature, humidity = current["temperature_2m"], current["relative_humidity_2m"]
    data_time, zone = current["time"], weather["timezone"]
    for value in (temperature, humidity):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("缺少有效温湿度")
    if not 0 <= humidity <= 100 or not data_time or not zone:
        raise ValueError("天气数据不完整")
    return (
        f"【在线天气查询】\n城市：{_place_name(place)}\n"
        f"数据时间：{data_time}（{zone}）\n"
        f"室外气温：{temperature}℃\n室外相对湿度：{humidity}%\n"
        "来源：Open-Meteo（https://open-meteo.com/），地名数据来自 GeoNames。\n"
        "说明：当前天气为天气模型估计，不是用户家中传感器实测；"
        "不能代替室内温湿度或长期气候。"
    )


def get_current_weather(city: str, region: str = "", country_code: str = "") -> str:
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            return _query_weather(client, city, region, country_code)
    except httpx.TimeoutException:
        return "天气查询超时，未取得当前天气。请稍后重试，或请用户提供当地温湿度；不要编造。"
    except httpx.HTTPStatusError:
        return "天气服务暂时不可用，未取得当前天气。请稍后重试或请用户提供温湿度。"
    except httpx.RequestError:
        return "无法连接天气服务，请检查网络或代理设置；本次没有取得天气数据。"
    except (ValueError, KeyError, TypeError):
        return "天气服务返回的数据不完整，无法可靠提供温湿度。请稍后重试，不要推测数值。"
