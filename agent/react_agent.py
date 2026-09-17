from langchain.agents import create_agent
from langchain_core.messages import AIMessage,ToolMessage
from model.factory import chat_model
from agent.tools.agent_tools import rag_summerize,get_weather,fetch_external_data,fill_context_for_report
from agent.tools.middleware import report_prompt_switch,monitor_tool,log_after_model,log_before_model
from utils.config_handle import agent_conf
from utils.prompt_handle import load_prompt



class ReactAgent:
    def __init__(self):

        self.messages = []

        self.agent = create_agent(
            model=chat_model,
            tools=[rag_summerize,get_weather,fetch_external_data,fill_context_for_report],
            middleware=[report_prompt_switch,monitor_tool,log_after_model,log_before_model] ,

            system_prompt=load_prompt(agent_conf["agent_prompt_path"]),

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


