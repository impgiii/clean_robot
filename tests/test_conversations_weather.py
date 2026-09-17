import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import httpx
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, messages_to_dict
from streamlit.testing.v1 import AppTest

from utils.conversation_store import ConversationStore, conversation_title
from utils import weather_service
from utils.config_handle import agent_conf


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'history.sqlite3'
        self.store = ConversationStore(self.path)

    def test_round_trip_full_tool_history_and_isolation(self):
        a, b = self.store.create(), self.store.create()
        messages = [HumanMessage(content='杭州天气'),
                    AIMessage(content='', tool_calls=[{'name':'get_weather','args':{'city':'杭州'},'id':'call_1','type':'tool_call'}]),
                    ToolMessage(content='天气数据', name='get_weather', tool_call_id='call_1'),
                    AIMessage(content='回答')]
        self.store.save_turn(a, 0, '杭州天气', '回答', messages)
        reopened = ConversationStore(self.path)
        self.assertEqual(messages_to_dict(reopened.load(a)['messages']), messages_to_dict(messages))
        self.assertEqual(reopened.load(a)['title'], '杭州天气')
        self.assertEqual(reopened.load(b)['messages'], [])
        self.assertEqual(reopened.load(b)['chat_history'], [])
        self.store.set_active(b)
        self.assertEqual(reopened.get_active(), b)

    def test_stale_save_and_delete_do_not_overwrite_or_resurrect(self):
        cid = self.store.create()
        self.store.save_turn(cid, 0, '问题', '回答', [])
        with self.assertRaises(RuntimeError):
            self.store.save_turn(cid, 0, '旧窗口', '覆盖', [])
        self.assertEqual(len(self.store.load(cid)['chat_history']), 2)
        self.store.set_active(cid)
        self.store.delete(cid)
        self.assertIsNone(self.store.get_active())
        with self.assertRaises(RuntimeError):
            self.store.save_turn(cid, 1, '问题', '回答', [])
        self.assertIsNone(self.store.load(cid))

    def test_legacy_migration_idempotent_and_titles(self):
        history = [{'role':'user','content':'我家是木地板'}, {'role':'assistant','content':'知道了'}]
        self.store.import_snapshot('legacy', history, history)
        self.store.import_snapshot('legacy', [], [])
        self.assertEqual(self.store.load('legacy')['chat_history'], history)
        self.assertEqual(conversation_title([]), '新对话')
        self.assertEqual(conversation_title([{'role':'user','content':'x'*25}]), 'x'*18+'…')


CITY = {'id':1,'name':'杭州','admin1':'浙江','country':'中国','country_code':'CN',
        'latitude':30.27,'longitude':120.15,'feature_code':'PPLA'}
WEATHER = {'current':{'temperature_2m':25.5,'relative_humidity_2m':70,'time':'2026-09-17T14:00'},
           'timezone':'Asia/Shanghai'}
REAL_CLIENT = httpx.Client


class WeatherTests(unittest.TestCase):
    def query(self, handler, city='杭州', region='', country_code=''):
        with patch.object(weather_service.httpx, 'Client',
                          side_effect=lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw)):
            return weather_service.get_current_weather(city, region, country_code)

    def test_new_city_and_source_time(self):
        requests = []
        def handler(request):
            requests.append(request)
            data = {'results':[CITY]} if 'geocoding' in request.url.host else WEATHER
            return httpx.Response(200, json=data)
        result = self.query(handler, '杭州市', '浙江', 'cn')
        self.assertIn('25.5℃', result)
        self.assertIn('70%', result)
        self.assertIn('2026-09-17T14:00', result)
        self.assertIn('Open-Meteo', result)
        self.assertIn('天气模型估计', result)
        self.assertEqual(requests[0].url.params['name'], '杭州, 浙江')
        self.assertEqual(requests[0].url.params['countryCode'], 'CN')
        self.assertIn('relative_humidity_2m', requests[1].url.params['current'])

    def test_ambiguous_does_not_call_forecast(self):
        other = dict(CITY, id=2, admin1='其他省', latitude=31)
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, json={'results':[CITY, other]})
        self.assertIn('确认', self.query(handler))
        self.assertEqual(len(calls), 1)

    def test_unknown_city(self):
        self.assertIn('没有找到', self.query(lambda req: httpx.Response(200, json={})))

    def test_timeout_and_network(self):
        for error, expected in [(httpx.ReadTimeout('timeout'), '超时'),
                                (httpx.ConnectError('offline'), '无法连接')]:
            with self.subTest(error=error):
                def handler(request):
                    raise error
                self.assertIn(expected, self.query(handler))

    def test_bad_status_and_malformed_payload(self):
        for status, data in [(429, {}), (200, {'error':True}), (200, {'results':'bad'})]:
            with self.subTest(status=status, data=data):
                result = self.query(lambda req: httpx.Response(status, json=data))
                self.assertNotIn('【在线天气查询】', result)
                self.assertTrue('不可用' in result or '不完整' in result)

    def test_missing_weather_is_not_success(self):
        def handler(request):
            data = {'results':[CITY]} if 'geocoding' in request.url.host else {'current':{}}
            return httpx.Response(200, json=data)
        self.assertIn('不完整', self.query(handler))


class FakeAgent:
    def __init__(self):
        self.messages = []

    def execute(self, question):
        if question == '模拟失败':
            yield '半截回答'
            raise RuntimeError('test failure')
        facts = ' '.join(m.content for m in self.messages if isinstance(m, HumanMessage))
        answer = '木地板' if '木地板' in facts + question else '瓷砖' if '瓷砖' in facts + question else '没有记录'
        yield answer[:1]
        self.messages = self.messages + [HumanMessage(content=question), AIMessage(content=answer)]
        yield answer


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / 'ui.sqlite3'
        self.config_patch = patch.dict(agent_conf, {'conversation_db_path':str(self.db_path)})
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        module = ModuleType('agent.react_agent')
        module.ReactAgent = FakeAgent
        self.module_patch = patch.dict(sys.modules, {'agent.react_agent':module})
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.app_path = str(Path(__file__).resolve().parents[1] / 'app.py')

    def launch(self):
        app = AppTest.from_file(self.app_path).run(timeout=15)
        self.assertFalse(app.exception)
        return app

    def ask(self, app, question):
        app.chat_input[0].set_value(question).run(timeout=15)
        self.assertFalse(app.exception)

    def test_create_switch_reload_delete_and_titles(self):
        app = self.launch()
        self.ask(app, '我家是木地板')
        a = app.session_state['active_conversation_id']
        self.assertEqual(app.subheader[0].value, '我家是木地板')
        app.button(key='new_conversation').click().run()
        b = app.session_state['active_conversation_id']
        self.assertNotEqual(a, b)
        self.ask(app, '我家是瓷砖')
        app.button(key='switch_' + a).click().run()
        self.ask(app, '什么地板？')
        self.assertEqual(app.chat_message[-1].markdown[0].value, '木地板')
        app.button(key='switch_' + b).click().run()
        self.ask(app, '什么地板？')
        self.assertEqual(app.chat_message[-1].markdown[0].value, '瓷砖')
        # 全新页面会话从 SQLite 恢复；不复用此前的 Agent 实例。
        restarted = self.launch()
        self.assertEqual(restarted.session_state['active_conversation_id'], b)
        self.ask(restarted, '什么地板？')
        self.assertEqual(restarted.chat_message[-1].markdown[0].value, '瓷砖')
        restarted.button(key='delete_conversation').click().run()
        self.assertEqual(restarted.session_state['active_conversation_id'], a)
        restarted.button(key='delete_conversation').click().run()
        self.assertFalse(restarted.exception)
        self.assertEqual(len(restarted.chat_message), 0)
        self.assertEqual(len(ConversationStore(self.db_path).list_conversations()), 1)

    def test_failed_turn_not_saved_and_no_memory_pollution(self):
        app = self.launch()
        self.ask(app, '我家是木地板')
        cid = app.session_state['active_conversation_id']
        self.ask(app, '模拟失败')
        self.assertEqual(len(app.error), 1)
        store = ConversationStore(self.db_path)
        self.assertEqual(len(store.load(cid)['chat_history']), 2)
        self.assertEqual(len(app.session_state['conversation_agents'][cid].messages), 2)
        self.ask(app, '什么地板？')
        self.assertEqual(app.chat_message[-1].markdown[0].value, '木地板')

    def test_migrate_existing_browser_session(self):
        app = AppTest.from_file(self.app_path)
        agent = FakeAgent()
        list(agent.execute('我家是木地板'))
        app.session_state['conversations'] = {'legacy':{'agent':agent,'title':'新对话',
            'chat_history':[{'role':'user','content':'我家是木地板'},{'role':'assistant','content':'木地板'}]}}
        app.session_state['active_conversation_id'] = 'legacy'
        app.run(timeout=15)
        self.assertFalse(app.exception)
        self.assertEqual(app.subheader[0].value, '我家是木地板')
        self.ask(app, '什么地板？')
        self.assertEqual(app.chat_message[-1].markdown[0].value, '木地板')


if __name__ == '__main__':
    unittest.main(verbosity=2)
