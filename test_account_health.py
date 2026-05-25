import os
import tempfile
import unittest

os.environ['TW_WEB_DATA_DIR'] = tempfile.mkdtemp(prefix='twitter-account-health-')
os.environ['TW_WEB_PUBLIC'] = '0'

from web_app import account_health_status, validate_account_cookie  # noqa: E402


class AccountHealthStatusTest(unittest.TestCase):
    def test_http_404_check_error_is_not_expired(self):
        self.assertEqual(account_health_status(False, 'HTTP 404: {"errors":[{"message":"Sorry"}]}'), 'unknown')

    def test_missing_cookie_parts_are_expired(self):
        self.assertEqual(account_health_status(False, '缺少 auth_token'), 'expired')
        self.assertEqual(account_health_status(False, '缺少 ct0'), 'expired')

    def test_auth_status_codes_are_auth_expired(self):
        self.assertEqual(account_health_status(False, 'HTTP 401: unauthorized'), 'auth_expired')
        self.assertEqual(account_health_status(False, 'HTTP 403: forbidden'), 'auth_expired')

    def test_network_check_error_is_check_failed(self):
        self.assertEqual(account_health_status(False, 'timed out while connecting'), 'check_failed')

    def test_validate_cookie_requires_auth_token_before_remote_check(self):
        ok, screen_name, error = validate_account_cookie('ct0=abc;')
        self.assertFalse(ok)
        self.assertIsNone(screen_name)
        self.assertEqual(error, '缺少 auth_token')


if __name__ == '__main__':
    unittest.main()
