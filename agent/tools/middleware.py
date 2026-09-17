from langchain.agents.middleware import dynamic_prompt,ModelRequest,wrap_tool_call,before_model,after_model
from langchain_core.messages import HumanMessage,ToolMessage,AIMessage
from utils.config_handle import agent_conf
from utils.prompt_handle import load_prompt
from time import perf_counter
from utils.logger_handle import logger
from langchain.agents import AgentState
from langgraph.runtime import Runtime

report_prompt = load_prompt(agent_conf["report_prompt_path"],)

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

@wrap_tool_call
def monitor_tool(request,handler):
    tool_name = request.tool_call["name"]
    call_id = request.tool_call.get("id","-")
    started = perf_counter()

    logger.info(
        "工具开始 | name=%s | id=%s",
        tool_name,
        call_id,
    )

    try:
        res = handler(request)
    except Exception as e:
        logger.exception(
            "工具异常 | name=%s | id=%s | 耗时=%.2f秒",
            tool_name,
            call_id,
            perf_counter() - started
        )
        raise

    elapsed = perf_counter() - started

    if isinstance(res,ToolMessage) and res.status == "error":
        logger.warning(
            "工具返回错误 | name=%s | id=%s | 耗时=%.2f秒",
            tool_name,
            call_id,
            elapsed,
        )

    else:
        logger.info(
            "工具正常返回 | name=%s | id=%s | 耗时=%.2f秒",
            tool_name,
            call_id,
            elapsed,
        )

    return res

@before_model
def log_before_model(state:AgentState,runtime:Runtime):
    messages = state["messages"]

    logger.info(
        "模型调用开始 | 状态消息数=%s | 最后一条类型=%s",
        len(messages),
        type(messages[-1]).__name__ if messages else "无",
    )
    return None

@after_model
def log_after_model(state:AgentState,runtime:Runtime):
    message = state["messages"][-1]

    if isinstance(message,AIMessage):
        if message.tool_calls:
            tool_names = [
               call["name"]
               for call in message.tool_calls
            ]
            logger.info(
                "模型返回 | 请求调用工具=%s",",".join(tool_names),
            )
        else:
            logger.info(
                "模型返回 | 无工具调用 | 文本字符数=%s",
                len(message.text),
            )

    return None













