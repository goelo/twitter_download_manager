import os
import tempfile
import time
import unittest

os.environ['TW_WEB_DATA_DIR'] = tempfile.mkdtemp(prefix='twitter-runtime-web-')
os.environ['TW_THROTTLE_DIR'] = tempfile.mkdtemp(prefix='twitter-runtime-throttle-')
os.environ['TW_ACCOUNT_API_INTERVAL_SECONDS'] = '0.05'
os.environ['TW_PROXY_API_INTERVAL_SECONDS'] = '0'
os.environ['TW_CRAWLER_REQUEST_RETRIES'] = '1'
os.environ['TW_WEB_PUBLIC'] = '0'

import crawler_runtime  # noqa: E402
import web_app  # noqa: E402


class CrawlerRuntimeTest(unittest.TestCase):
    def test_classify_http_statuses(self):
        self.assertEqual(crawler_runtime.classify_response(401), 'auth_expired')
        self.assertEqual(crawler_runtime.classify_response(403), 'auth_expired')
        self.assertEqual(crawler_runtime.classify_response(429), 'rate_limited')
        self.assertEqual(crawler_runtime.classify_response(404), 'target_unavailable')
        self.assertEqual(crawler_runtime.classify_response(503), 'network_failed')

    def test_classify_exception_text(self):
        self.assertEqual(crawler_runtime.classify_exception(RuntimeError('proxy timeout')), 'network_failed')
        self.assertEqual(crawler_runtime.classify_exception(RuntimeError('Rate limit exceeded')), 'rate_limited')
        self.assertEqual(crawler_runtime.classify_exception(RuntimeError('HTTP 403')), 'auth_expired')

    def test_file_throttle_reserves_account_interval(self):
        limits = crawler_runtime.RuntimeLimits(account_api_interval=0.05, proxy_api_interval=0, max_retries=1, backoff_base=0.1)
        throttle = crawler_runtime.FileThrottle(base_dir=os.environ['TW_THROTTLE_DIR'], limits=limits)
        start = time.monotonic()
        throttle.wait('account-a')
        throttle.wait('account-a')
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.04)

    def test_web_failure_classification_uses_structured_marker(self):
        error_type, message = web_app.classify_failure('CRAWLER_ERROR_TYPE=rate_limited\nanything', 1)
        self.assertEqual(error_type, 'rate_limited')
        self.assertIn('超限', message)


if __name__ == '__main__':
    unittest.main()
