import streamlit as st

from agent.react_agent import ReactAgent
from utils.config_handle import agent_conf
from utils.conversation_store import ConversationStore
from utils.logger_handle import logger
from utils.path_tool import get_abs_path


st.set_page_config(page_title="扫地机器人客服", page_icon="😇")
st.title("扫地机器人智能客服")
st.caption("支持选购咨询、使用排查和示例使用报告；天气来自在线服务。")

store = ConversationStore(get_abs_path(agent_conf["conversation_db_path"]))

# 热更新时，将旧版尚在内存中的对话迁移到本地数据库。
if "conversations" in st.session_state:
    for old_id, old in st.session_state.conversations.items():
        store.import_snapshot(old_id, old["chat_history"], old["agent"].messages)
    del st.session_state["conversations"]

if "conversation_agents" not in st.session_state:
    st.session_state.conversation_agents = {}


def select_conversation(conversation_id):
    st.session_state.active_conversation_id = conversation_id
    store.set_active(conversation_id)


conversations = store.list_conversations()
if not conversations:
    select_conversation(store.create())
    conversations = store.list_conversations()

known_ids = {item["id"] for item in conversations}
active_id = st.session_state.get("active_conversation_id", store.get_active())
if active_id not in known_ids:
    active_id = conversations[0]["id"]
select_conversation(active_id)

# 清除被另一个窗口删除的 Agent 缓存。
for cached_id in list(st.session_state.conversation_agents):
    if cached_id not in known_ids:
        del st.session_state.conversation_agents[cached_id]

with st.sidebar:
    st.header("我的对话")
    st.caption("记录保存在本机，刷新或重启后可继续。")
    if st.button("＋ 新建对话", key="new_conversation"):
        select_conversation(store.create())
        st.rerun()

    if st.button("删除当前对话", key="delete_conversation"):
        store.delete(active_id)
        st.session_state.conversation_agents.pop(active_id, None)
        remaining = store.list_conversations()
        select_conversation(remaining[0]["id"] if remaining else store.create())
        st.rerun()

    st.divider()
    for item in conversations:
        prefix = "● " if item["id"] == active_id else ""
        if st.button(prefix + item["title"], key=f"switch_{item['id']}"):
            select_conversation(item["id"])
            st.rerun()

current = store.load(active_id)
if current is None:
    st.rerun()
st.subheader(current["title"])
for message in current["chat_history"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("请输入你的问题", key=f"chat_input_{active_id}")
if question and question.strip():
    question = question.strip()
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        agent = None
        try:
            with st.spinner("正在处理你的问题……"):
                if active_id not in st.session_state.conversation_agents:
                    st.session_state.conversation_agents[active_id] = ReactAgent()
                agent = st.session_state.conversation_agents[active_id]
                # 完整恢复 Human/AI/Tool 消息及工具调用 ID。
                agent.messages = current["messages"]
                answer = ""
                for text in agent.execute(question):
                    answer = text
                    placeholder.markdown(text + " ▌" if text else "正在查询资料……")
                if not answer.strip():
                    raise RuntimeError("没有获得完整回答")
                store.save_turn(active_id, current["revision"], question, answer, agent.messages)
        except Exception:
            if agent is not None:
                agent.messages = current["messages"]
            placeholder.empty()
            logger.exception("客服回答或保存失败 | conversation_id=%s", active_id)
            st.error("本次回答未完成或未能保存，请刷新后重试。此前的聊天记录仍保留。")
        else:
            # 保存后刷新标题，不会重复调用模型。
            st.rerun()
