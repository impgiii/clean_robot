from langchain.agents import create_agent
from langchain_core.messages import AIMessage,ToolMessage
from model.factory import chat_model
from agent.tools.agent_tools import rag_summerize,get_weather,fetch_external_data,fill_context_for_report
from agent.tools.middleware import report_prompt_switch



class ReactAgent:
    def __init__(self):

        self.messages = []

        self.agent = create_agent(
            model=chat_model,
            tools=[rag_summerize,get_weather,fetch_external_data,fill_context_for_report],
            middleware=[report_prompt_switch] ,

            system_prompt=(
            "你是扫地机器人客服。\n"
            "简单问候可以直接回复。\n"
            "涉及产品选购、使用、维护或故障排查时，"
            "调用 rag_summerize 获取有依据的回答。\n"

            "当问题确实需要当地温湿度、且用户尚未提供这些数据时，"
            "可以调用 get_weather；缺少城市时先询问城市。\n"
            "用户已提供相关温湿度时，直接使用，不必重复查询。\n"

            "获取天气后，如果需要给出机器人建议，"
            "将原始问题、相关天气数据和用户已提供的家庭情况"
            "一起传给 rag_summerize。\n"

            "当前天气工具返回模拟数据，回答中必须明确说明这一点。\n"
            "室外天气不能直接当作室内温湿度，"
            "单次天气也不能代表当地长期气候。\n"

            "根据工具结果回答，保留来源和不确定性，"
            "不要编造产品参数、价格或售后政策。\n"
            "只追问影响当前判断的关键信息，"
            "不要重复询问用户已经提供的信息。"

            "查询个人使用情况或生成使用报告时，"
            "先调用 fetch_external_data 获取使用记录。\n"
            "当前使用的是本地示例数据，回复时应说明。\n"
            "缺少用户编号或明确月份时先询问，不能自行编造。\n"
            "记录不存在时明确告知，不能把其他用户或月份的数据当成目标记录。\n"
            "记录中的清洁指标和耗材情况以查询结果为准，"
            "不要用通用知识库代替个人使用记录。\n"

            "用户明确要求生成使用报告时，先查询目标用户和月份的记录。\n"
            "查询到有效记录后，调用 fill_context_for_report，"
            "然后按照报告要求生成回答。\n"
            "缺少用户编号或月份时先追问，记录不存在时不进入报告模式。\n"
            "只查询某个指标时，直接根据记录回答，不必进入报告模式。\n"
            ),
        )

    def execute(self,question,debug:bool=False):
        question = question.strip()
        if not question:
            yield "请输入你的问题。"
            return

        input_messages = self.messages+[
            {"role":"user","content":question},
        ]

        final_state = None
        last_run = None
        draft = ""

        for mode,data in self.agent.stream(
        {"messages":input_messages},
            stream_mode=["messages","values"],
        ):
            if mode == "values":
                final_state = data
                last_message = data["messages"][-1]

                if (
                    isinstance(last_message,AIMessage)
                    and last_message.tool_calls
                ):
                    draft = ""
                    last_run = None
                    yield ""

                continue

            chunk,metadata = data

            if metadata.get("langgraph_node") != "model":
                continue

            run = (metadata.get("langgraph_step"),chunk.id)
            if run != last_run:
                draft = ""
                last_run = run

            if chunk.text:
                draft += chunk.text
                yield draft

        if final_state is None:
            raise RuntimeError("未收到执行结果")

        final_message = final_state["messages"][-1]

        if (
            not isinstance(final_message,AIMessage)
            or final_message.tool_calls
            or not final_message.text.strip()
        ):
            raise RuntimeError("未获得完整的文字回复")

        self.messages = final_state["messages"]

        yield final_message.text



    def clear_history(self):
        self.messages = []


