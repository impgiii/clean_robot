"""本机单用户对话存储：同时保存展示记录和完整的 Agent 消息。"""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from langchain_core.messages import convert_to_messages, messages_from_dict, messages_to_dict


def conversation_title(history):
    first_question = next((item["content"] for item in history if item["role"] == "user"), "")
    text = " ".join(first_question.split())
    return (text[:18] + ("…" if len(text) > 18 else "")) or "新对话"


class ConversationStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL,
                    chat_history TEXT NOT NULL, messages TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0
                )
            """)
            db.execute("CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def list_conversations(self):
        with closing(self._connect()) as db:
            return [dict(row) for row in db.execute(
                "SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC, id DESC"
            )]

    def load(self, conversation_id):
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["chat_history"] = json.loads(result["chat_history"])
        result["messages"] = messages_from_dict(json.loads(result["messages"]))
        return result

    def create(self):
        return self.import_snapshot(uuid4().hex, [], [])

    def import_snapshot(self, conversation_id, history, messages):
        """迁移升级前尚在 Streamlit 内存中的对话；已有记录不覆盖。"""
        now = datetime.now(timezone.utc).isoformat()
        message_data = messages_to_dict(convert_to_messages(messages))
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO conversations "
                "(id,title,chat_history,messages,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                (conversation_id, conversation_title(history), json.dumps(history, ensure_ascii=False),
                 json.dumps(message_data, ensure_ascii=False), now, now),
            )
        return conversation_id

    def save_turn(self, conversation_id, revision, question, answer, messages):
        """一次提交展示记录和工具消息；拒绝覆盖其他窗口已修改的对话。"""
        with closing(self._connect()) as db, db:
            row = db.execute(
                "SELECT chat_history FROM conversations WHERE id = ? AND revision = ?",
                (conversation_id, revision),
            ).fetchone()
            if row is None:
                raise RuntimeError("该对话已在其他窗口修改或删除，请刷新后重试。")
            history = json.loads(row["chat_history"])
            history.extend([{"role": "user", "content": question}, {"role": "assistant", "content": answer}])
            message_data = messages_to_dict(convert_to_messages(messages))
            cursor = db.execute(
                "UPDATE conversations SET title=?, chat_history=?, messages=?, updated_at=?, "
                "revision=revision+1 WHERE id=? AND revision=?",
                (conversation_title(history), json.dumps(history, ensure_ascii=False),
                 json.dumps(message_data, ensure_ascii=False), datetime.now(timezone.utc).isoformat(),
                 conversation_id, revision),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("该对话已更新，请刷新后重试。")

    def delete(self, conversation_id):
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            db.execute("DELETE FROM settings WHERE name='active_conversation' AND value=?", (conversation_id,))

    def get_active(self):
        with closing(self._connect()) as db:
            row = db.execute("SELECT value FROM settings WHERE name='active_conversation'").fetchone()
        return row["value"] if row else None

    def set_active(self, conversation_id):
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO settings(name,value) VALUES ('active_conversation',?) "
                "ON CONFLICT(name) DO UPDATE SET value=excluded.value", (conversation_id,),
            )
