import asyncio
import contextlib
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx

from proxy_utils import proxy_for_httpx
from url_utils import quote_url


AUTHORIZATION = 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA'
DEFAULT_TIMEOUT = (3.05, 16)


class CrawlerError(RuntimeError):
    def __init__(self, error_type, message, status_code=None):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code


def classify_response(status_code, text=''):
    lower = str(text or '').lower()
    if status_code in {401, 403}:
        return 'auth_expired'
    if status_code == 429 or 'rate limit exceeded' in lower or 'api次数已超限' in text:
        return 'rate_limited'
    if status_code == 404:
        return 'target_unavailable'
    if status_code in {408, 409, 425, 500, 502, 503, 504}:
        return 'network_failed'
    return 'failed'


def classify_exception(exc):
    if isinstance(exc, CrawlerError):
        return exc.error_type
    text = str(exc).lower()
    if any(term in text for term in ['401', '403', 'auth', 'cookie', 'ct0']):
        return 'auth_expired'
    if '429' in text or 'rate limit' in text or 'api次数已超限' in str(exc):
        return 'rate_limited'
    if any(term in text for term in ['timeout', 'timed out', 'connect', 'network', 'proxy', 'readerror']):
        return 'network_failed'
    if '404' in text or 'not found' in text:
        return 'target_unavailable'
    return 'failed'


def raise_for_crawler_response(response):
    if response.status_code < 400:
        text = response.text
        if 'Rate limit exceeded' in text or 'API次数已超限' in text:
            raise CrawlerError('rate_limited', 'Rate limit exceeded', response.status_code)
        return
    error_type = classify_response(response.status_code, response.text[:500])
    raise CrawlerError(error_type, f'HTTP {response.status_code}: {response.text[:200]}', response.status_code)


def ct0_from_cookie(cookie):
    match = re.search(r'ct0=([^;]+)', str(cookie or ''))
    if not match:
        raise CrawlerError('auth_expired', 'Cookie missing ct0')
    return match.group(1)


def standard_headers(cookie, referer='https://twitter.com/'):
    return {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'authorization': AUTHORIZATION,
        'cookie': cookie,
        'x-csrf-token': ct0_from_cookie(cookie),
        'referer': referer,
    }


def resource_key(value):
    text = str(value or 'none')
    return quote(text, safe='')[:180] or 'none'


@dataclass
class RuntimeLimits:
    account_api_interval: float = 2.0
    proxy_api_interval: float = 0.5
    media_download_interval: float = 0.0
    max_retries: int = 3
    backoff_base: float = 1.0

    @classmethod
    def from_env(cls):
        return cls(
            account_api_interval=float(os.environ.get('TW_ACCOUNT_API_INTERVAL_SECONDS', '2') or 2),
            proxy_api_interval=float(os.environ.get('TW_PROXY_API_INTERVAL_SECONDS', '0.5') or 0.5),
            media_download_interval=float(os.environ.get('TW_MEDIA_DOWNLOAD_INTERVAL_SECONDS', '0') or 0),
            max_retries=max(1, int(os.environ.get('TW_CRAWLER_REQUEST_RETRIES', '3') or 3)),
            backoff_base=max(0.1, float(os.environ.get('TW_CRAWLER_BACKOFF_BASE_SECONDS', '1') or 1)),
        )


class FileThrottle:
    def __init__(self, base_dir=None, limits=None):
        self.base_dir = Path(base_dir or os.environ.get('TW_THROTTLE_DIR') or Path.cwd() / 'web_data' / 'throttle')
        self.limits = limits or RuntimeLimits.from_env()
        self._local_lock = threading.Lock()

    def wait(self, account_key='', proxy_key='', media_key=''):
        waits = []
        if account_key and self.limits.account_api_interval > 0:
            waits.append(self._reserve('account', account_key, self.limits.account_api_interval))
        if proxy_key and self.limits.proxy_api_interval > 0:
            waits.append(self._reserve('proxy', proxy_key, self.limits.proxy_api_interval))
        if media_key and self.limits.media_download_interval > 0:
            waits.append(self._reserve('media', media_key, self.limits.media_download_interval))
        delay = max(waits or [0])
        if delay > 0:
            time.sleep(delay)

    async def async_wait(self, account_key='', proxy_key='', media_key=''):
        waits = []
        if account_key and self.limits.account_api_interval > 0:
            waits.append(self._reserve('account', account_key, self.limits.account_api_interval))
        if proxy_key and self.limits.proxy_api_interval > 0:
            waits.append(self._reserve('proxy', proxy_key, self.limits.proxy_api_interval))
        if media_key and self.limits.media_download_interval > 0:
            waits.append(self._reserve('media', media_key, self.limits.media_download_interval))
        delay = max(waits or [0])
        if delay > 0:
            await asyncio.sleep(delay)

    def _reserve(self, scope, key, interval):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / f'{scope}-{resource_key(key)}.txt'
        lock_path = self.base_dir / f'{scope}-{resource_key(key)}.lock'
        with self._local_lock, cross_process_lock(lock_path):
            now_ts = time.monotonic()
            previous = 0.0
            if path.exists():
                try:
                    previous = float(path.read_text(encoding='utf-8') or '0')
                except ValueError:
                    previous = 0.0
            available_at = max(now_ts, previous + interval)
            path.write_text(str(available_at), encoding='utf-8')
        return max(0.0, available_at - now_ts)


@contextlib.contextmanager
def cross_process_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, 'a+', encoding='utf-8')
    try:
        if os.name == 'nt':
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.01)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


class CrawlerClient:
    def __init__(self, cookie='', proxy='', account_key='', throttle=None, headers=None):
        self.cookie = cookie
        self.proxy = proxy_for_httpx(proxy)
        self.account_key = account_key or cookie
        self.proxy_key = proxy or ''
        self.throttle = throttle or FileThrottle()
        self.headers = dict(headers or standard_headers(cookie))
        self.limits = RuntimeLimits.from_env()

    def get_text(self, url, headers=None, timeout=DEFAULT_TIMEOUT, quote=True):
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)
        return self._request_with_retries(url, request_headers, timeout, quote).text

    def get_bytes(self, url, headers=None, timeout=DEFAULT_TIMEOUT, quote=True):
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)
        return self._request_with_retries(url, request_headers, timeout, quote).content

    def get_media_bytes(self, url, headers=None, timeout=DEFAULT_TIMEOUT, quote=True):
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)
        return self._request_with_retries(url, request_headers, timeout, quote, media=True).content

    def _request_with_retries(self, url, headers, timeout, should_quote, media=False):
        last_error = None
        for attempt in range(1, self.limits.max_retries + 1):
            try:
                self.throttle.wait(self.account_key if not media else '', self.proxy_key if not media else '', self.proxy_key or self.account_key if media else '')
                response = httpx.get(quote_url(url) if should_quote else url, headers=headers, proxy=self.proxy, timeout=timeout)
                raise_for_crawler_response(response)
                return response
            except Exception as exc:
                last_error = exc
                error_type = classify_exception(exc)
                if error_type in {'auth_expired', 'target_unavailable'} or attempt >= self.limits.max_retries:
                    if isinstance(exc, CrawlerError):
                        raise
                    raise CrawlerError(error_type, str(exc)) from exc
                time.sleep(self.limits.backoff_base * attempt)
        raise CrawlerError(classify_exception(last_error), str(last_error))


class AsyncCrawlerClient:
    def __init__(self, cookie='', proxy='', account_key='', throttle=None, headers=None, max_connections=8):
        self.cookie = cookie
        self.proxy = proxy_for_httpx(proxy)
        self.account_key = account_key or cookie
        self.proxy_key = proxy or ''
        self.throttle = throttle or FileThrottle()
        self.headers = dict(headers or standard_headers(cookie))
        self.limits = RuntimeLimits.from_env()
        limits = httpx.Limits(max_connections=max_connections, max_keepalive_connections=max_connections)
        self.client = httpx.AsyncClient(proxy=self.proxy, limits=limits)

    async def aclose(self):
        await self.client.aclose()

    async def get(self, url, headers=None, timeout=DEFAULT_TIMEOUT, quote=True, media=False):
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)
        last_error = None
        for attempt in range(1, self.limits.max_retries + 1):
            try:
                await self.throttle.async_wait(self.account_key if not media else '', self.proxy_key if not media else '', self.proxy_key or self.account_key if media else '')
                response = await self.client.get(quote_url(url) if quote else url, headers=request_headers, timeout=timeout)
                raise_for_crawler_response(response)
                return response
            except Exception as exc:
                last_error = exc
                error_type = classify_exception(exc)
                if error_type in {'auth_expired', 'target_unavailable'} or attempt >= self.limits.max_retries:
                    if isinstance(exc, CrawlerError):
                        raise
                    raise CrawlerError(error_type, str(exc)) from exc
                await asyncio.sleep(self.limits.backoff_base * attempt)
        raise CrawlerError(classify_exception(last_error), str(last_error))
