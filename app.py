from utils.logger_handle import logger
import streamlit as st
from agent.react_agent import ReactAgent

st.set_page_config(
    page_title="扫地机器人客服",
    page_icon="😇",
)

st.title("扫地机器人智能客服")
st.caption("支持选购咨询、使用排查和示例使用报告，天气为模拟数据。")

if "agent" not in st.session_state:
    st.session_state.agent = ReactAgent()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if st.sidebar.button("开启新对话"):
    st.session_state.agent.clear_history()
    st.session_state.chat_history = []
    st.rerun()

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("请输入你的问题")

if question:
    question = question.strip()
    if not question:
        st.stop()

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        answer = ""

        try:
            with st.spinner("正在处理你的问题……"):
                for text in st.session_state.agent.execute(question):
                    answer = text

                    if text:
                        placeholder.markdown(text + " ▌")
                    else:
                        placeholder.markdown("正在查询资料……")

        except Exception:
            placeholder.empty()
            logger.exception("客服流式回答失败")
            st.error("本次回答未完成，请稍后重试。")

        else:
            placeholder.markdown(answer)

            st.session_state.chat_history.extend([
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ])
