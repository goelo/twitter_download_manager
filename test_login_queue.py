import os
import tempfile
import time
import unittest

os.environ['TW_WEB_DATA_DIR'] = tempfile.mkdtemp(prefix='twitter-login-queue-')
os.environ['TW_WEB_PUBLIC'] = '0'

import web_app  # noqa: E402


class LoginQueueTest(unittest.TestCase):
    def setUp(self):
        web_app.init_db()
        web_app.BROWSER_LOGIN_DISABLED = False
        web_app.local_login_helper_process = None
        with web_app.local_browser_login_lock:
            with web_app.login_queue_lock:
                web_app.local_browser_login_sessions.clear()
                web_app.login_queue_items.clear()
                web_app.login_queue_counter = 0
        with web_app.db() as conn:
            conn.execute('delete from accounts')

    def test_sanitize_label_extracts_username_and_redacts_secrets(self):
        label = web_app.sanitize_login_queue_label(
            '用户名demo_user 密码Secret123 邮箱a@example.com 验证码获取链接https://2fa.example/test'
        )
        self.assertEqual(label, 'demo_user')

        redacted = web_app.sanitize_login_queue_label('密码Secret123 邮箱a@example.com https://2fa.example/test')
        self.assertNotIn('Secret123', redacted)
        self.assertNotIn('a@example.com', redacted)
        self.assertNotIn('https://2fa.example', redacted)

    def test_parse_raw_account_text_extracts_multiple_usernames(self):
        raw = (
            '用户名first_user密码SecretA邮箱first@example.com邮箱密码MailA验证码获取链接https://2fa.example/a\n'
            '用户名second_user密码SecretB邮箱second@example.com邮箱密码MailB验证码获取链接https://2fa.example/b'
        )

        parsed = web_app.parse_login_queue_text(raw)

        self.assertEqual([item['label'] for item in parsed['items']], ['first_user', 'second_user'])
        self.assertGreaterEqual(parsed['sensitive_fields_removed'], 8)
        self.assertEqual(parsed['duplicates'], [])

    def test_parse_raw_account_text_dedupes_and_skips_without_secret_echo(self):
        raw = '用户名dup_user 密码SecretA\n用户名dup_user 密码SecretB\n密码OnlySecret 邮箱hidden@example.com https://2fa.example/c'

        parsed = web_app.parse_login_queue_text(raw)
        visible = str(parsed)

        self.assertEqual([item['label'] for item in parsed['items']], ['dup_user'])
        self.assertEqual(parsed['duplicates'], [{'label': 'dup_user'}])
        self.assertNotIn('SecretA', visible)
        self.assertNotIn('SecretB', visible)
        self.assertNotIn('hidden@example.com', visible)
        self.assertNotIn('https://2fa.example', visible)

    def test_normalize_login_queue_labels_uses_parser_for_pasted_text(self):
        labels = web_app.normalize_login_queue_labels({'text': '用户名first 密码A 用户名second 密码B'})
        self.assertEqual(labels, ['first', 'second'])

    def test_queue_starts_only_one_running_item(self):
        labels = web_app.normalize_login_queue_labels({'text': 'first\nsecond'})
        with web_app.local_browser_login_lock:
            with web_app.login_queue_lock:
                for label in labels:
                    web_app.login_queue_counter += 1
                    web_app.login_queue_items.append(
                        {
                            'id': web_app.login_queue_counter,
                            'label': label,
                            'status': 'pending',
                            'message': '等待登录',
                            'created_at': time.time(),
                            'user_id': 1,
                        }
                    )
                web_app.login_queue_start_next_locked(user_id=1)

        statuses = [item['status'] for item in web_app.login_queue_items]
        self.assertEqual(statuses, ['running', 'pending'])
        self.assertEqual(len(web_app.local_browser_login_sessions), 1)

    def test_terminal_payload_advances_to_next_item(self):
        with web_app.local_browser_login_lock:
            with web_app.login_queue_lock:
                for label in ['first', 'second']:
                    web_app.login_queue_counter += 1
                    web_app.login_queue_items.append(
                        {
                            'id': web_app.login_queue_counter,
                            'label': label,
                            'status': 'pending',
                            'message': '等待登录',
                            'created_at': time.time(),
                            'user_id': 1,
                        }
                    )
                first = web_app.login_queue_start_next_locked(user_id=1)

        web_app.login_queue_mark_terminal_from_payload(
            first['id'],
            {'status': 'completed', 'message': '登录成功，账号已保存。', 'screen_name': 'first'},
            user_id=1,
        )

        self.assertEqual(web_app.login_queue_items[0]['status'], 'completed')
        self.assertEqual(web_app.login_queue_items[1]['status'], 'running')

    def test_expired_running_item_advances_queue(self):
        with web_app.local_browser_login_lock:
            with web_app.login_queue_lock:
                for label in ['first', 'second']:
                    web_app.login_queue_counter += 1
                    web_app.login_queue_items.append(
                        {
                            'id': web_app.login_queue_counter,
                            'label': label,
                            'status': 'pending',
                            'message': '等待登录',
                            'created_at': time.time(),
                            'user_id': 1,
                        }
                    )
                first = web_app.login_queue_start_next_locked(user_id=1)
                token = first['token']
                web_app.local_browser_login_sessions[token]['expires_at'] = time.time() - 1
                web_app.login_queue_sync_expired_locked(user_id=1)

        self.assertEqual(web_app.login_queue_items[0]['status'], 'expired')
        self.assertEqual(web_app.login_queue_items[1]['status'], 'running')

    def test_ensure_local_login_helper_ready_does_not_start_process(self):
        original_health = web_app.local_login_helper_health
        original_start = web_app.start_local_login_helper_process
        started = []
        try:
            web_app.local_login_helper_health = lambda timeout=1.0: True
            web_app.start_local_login_helper_process = lambda: started.append(True)

            result = web_app.ensure_local_login_helper_running(wait_seconds=1)

            self.assertTrue(result['ok'])
            self.assertEqual(result['status'], 'ready')
            self.assertEqual(started, [])
        finally:
            web_app.local_login_helper_health = original_health
            web_app.start_local_login_helper_process = original_start

    def test_ensure_local_login_helper_starts_when_health_missing(self):
        original_health = web_app.local_login_helper_health
        original_start = web_app.start_local_login_helper_process

        class FakeProcess:
            def poll(self):
                return None

        calls = {'health': 0, 'start': 0}
        try:
            def fake_health(timeout=1.0):
                calls['health'] += 1
                return calls['health'] >= 3

            def fake_start():
                calls['start'] += 1
                return True, FakeProcess()

            web_app.local_login_helper_health = fake_health
            web_app.start_local_login_helper_process = fake_start

            result = web_app.ensure_local_login_helper_running(wait_seconds=2)

            self.assertTrue(result['ok'])
            self.assertEqual(result['status'], 'ready')
            self.assertEqual(calls['start'], 1)
        finally:
            web_app.local_login_helper_health = original_health
            web_app.start_local_login_helper_process = original_start

    def test_ensure_local_login_helper_respects_disabled_flag(self):
        original_disabled = web_app.BROWSER_LOGIN_DISABLED
        try:
            web_app.BROWSER_LOGIN_DISABLED = True
            with self.assertRaises(web_app.HTTPException) as ctx:
                web_app.ensure_local_login_helper_running(wait_seconds=1)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            web_app.BROWSER_LOGIN_DISABLED = original_disabled


if __name__ == '__main__':
    unittest.main()
