from langchain_core.tools import tool
from rag.rag_service import RagService
from utils.record_handle import get_usage_record

rag_service = RagService()

@tool
def rag_summerize(question:str)->str:
    """根据扫地机器人知识库回答选购、使用、维护和故障排查问题。
    question应该包含用户的问题，以及相关的型号和使用情况，返回基于资料生成的回答
    """
    return rag_service.answer(question)



@tool
def get_weather(city:str)->str:
    """
    获取指定城市的模拟温度和湿度，用于演示环境相关的机器人咨询
    city为用户指定的城市名称
    返回的是测试数据，不代表真实天气
    """
    city = city.strip().removesuffix("市")

    weather_data = {
        "北京":{"temperature":18,"humidity":30},
        "上海":{"temperature":25,"humidity":90},
        "广州":{"temperature":30,"humidity":70},
    }

    weather = weather_data.get(city)

    if weather is None:
        return (
            f"未提供{city}的模拟天气数据。"
            "请向用户询问相关天气数据，不可以自行编造。"
        )

    return (
        f"【模拟天气，不代表实时情况】\n"
        f"城市：{city}\n"
        f"室外气温：{weather['temperature']}℃\n"
        f"室外相对湿度：{weather['humidity']}%"
    )

@tool
def fetch_external_data(user_id,month)->str:
    """查询本地示例数据中的指定用户，指定月份的机器人使用记录
    user_id使用户编号，如：1001
    month必须使用yyyy-mm格式，比如2025-01
    返回使用记录，没有记录时要说明
    """
    record = get_usage_record(user_id,month)

    if record is None:
        return f"未找到用户{user_id}在{month}的使用记录。"

    parts = ["【本地示例使用记录】"]

    for key,value in record.items():
        text = value.replace("\\n","\n")
        parts.append(f"{key}:{text}")
        
    return ",".join(parts)