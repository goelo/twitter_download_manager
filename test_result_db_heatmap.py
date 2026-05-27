import os
import tempfile
import unittest

os.environ['TW_WEB_DATA_DIR'] = tempfile.mkdtemp(prefix='twitter-result-db-')
os.environ['TW_WEB_PUBLIC'] = '0'
os.environ['TW_WEB_CREDENTIAL_KEY'] = 'test-result-db-secret'

import web_app  # noqa: E402


class ResultDbHeatmapTest(unittest.TestCase):
    def setUp(self):
        web_app.init_db()

    def test_secret_payload_hides_encrypted_password(self):
        encrypted = web_app.encrypt_secret('db-password')
        with web_app.db() as conn:
            row_id = conn.execute(
                '''
                insert into result_db_configs
                  (label, db_type, host, port, database_name, username, encrypted_password, ssl_enabled, enabled, status, created_at, updated_at)
                values ('result', 'postgresql', 'localhost', 5432, 'analytics', 'user', ?, 0, 1, 'untested', ?, ?)
                ''',
                (encrypted, web_app.now(), web_app.now()),
            ).lastrowid
            row = conn.execute('select * from result_db_configs where id = ?', (row_id,)).fetchone()

        payload = web_app.result_db_payload(row)

        self.assertTrue(payload['has_password'])
        self.assertNotIn('password', payload)
        self.assertNotIn('encrypted_password', payload)
        self.assertEqual(web_app.decrypt_secret(encrypted), 'db-password')

    def test_local_heatmap_has_seven_days_and_hour_cells(self):
        with web_app.db() as conn:
            conn.execute(
                '''
                insert into task_items
                  (task_id, source_file, tweet_url, tweet_date, display_name, screen_name, content,
                   favorite_count, retweet_count, reply_count, media_count, created_at)
                values (1, 'result.csv', 'https://x.com/a/status/1', ?, 'A', 'a', 'hello', 0, 0, 0, 2, ?)
                ''',
                (web_app.now(), web_app.now()),
            )

        heatmap = web_app.local_result_heatmap(days=7)

        self.assertEqual(heatmap['source'], 'local')
        self.assertEqual(len(heatmap['dates']), 7)
        self.assertEqual(len(heatmap['hours']), 24)
        self.assertEqual(len(heatmap['cells']), 7 * 24)
        self.assertEqual(heatmap['total'], 1)
        self.assertEqual(heatmap['max_count'], 1)


if __name__ == '__main__':
    unittest.main()
