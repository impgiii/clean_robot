from langchain_core.tools import tool
from rag.rag_service import RagService
from utils.record_handle import get_usage_record
from utils.weather_service import get_current_weather

rag_service = RagService()

@tool
def rag_summerize(question:str)->str:
    """根据扫地机器人知识库回答选购、使用、维护和故障排查问题。
    question应该包含用户的问题，以及相关的型号和使用情况，返回基于资料生成的回答
    """
    return rag_service.answer(question)



@tool
def get_weather(city: str, region: str = "", country_code: str = "") -> str:
    """查询城市当前室外温度和湿度，返回地点、数据时间和来源。
    city 只填写城市名，例如杭州；已知省份可填 region，例如浙江。
    已知国家可填两位 country_code，例如 CN；信息未知时留空。
    重名城市需要向用户确认；失败时没有天气数据，不可编造。
    天气来自 Open-Meteo 天气模型，不代表室内实测或长期气候。
    """
    return get_current_weather(city, region, country_code)


@tool
def fetch_external_data(user_id:str,month:str)->str:
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
        
    return "\n".join(parts)

@tool
def fill_context_for_report()->str:
    """
    用户明确要求生成使用报告，且已经查到目标记录后，标记进入报告模式。
    仅仅查询某个指标时不需要调用。
    """
    return "已经进入了报告模式，请根据目标使用记录生成报告。"
