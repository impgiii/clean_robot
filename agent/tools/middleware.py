from langchain.agents.middleware import dynamic_prompt,ModelRequest
from langchain_core.messages import HumanMessage,ToolMessage
from utils.config_handle import agent_conf
from utils.path_tool import get_abs_path

report_prompt = get_abs_path(
    agent_conf["report_prompt_path"],
).read_text(encoding="utf-8")

@dynamic_prompt
def report_prompt_switch(request:ModelRequest)->str:
    base_prompt = (
        request.system_message.text
        if request.system_message is not None
        else ""
    )

    for message in reversed(request.state["messages"]):
        if isinstance(message, HumanMessage):
            break

        if(
            isinstance(message, ToolMessage)
            and message.name == "fill_context_for_report"
            and message.status == "success"
        ):
            return base_prompt + "\n\n" +report_prompt

    return base_prompt
