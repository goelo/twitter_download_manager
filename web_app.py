import hashlib
import json
import os
import signal
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path
from threading import Thread

import httpx
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'web_data'
TASKS_DIR = DATA_DIR / 'tasks'
DB_PATH = DATA_DIR / 'web.sqlite3'
DEFAULT_ADMIN_USER = os.environ.get('TW_WEB_ADMIN_USER', 'admin')
DEFAULT_ADMIN_PASSWORD = os.environ.get('TW_WEB_ADMIN_PASSWORD', 'admin123')
SESSION_SECRET = os.environ.get('TW_WEB_SESSION_SECRET', secrets.token_hex(32))

app = FastAPI(title='Twitter Download Web')
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site='lax')
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='static')
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))

worker_lock = threading.Lock()
worker_thread = None
stop_worker = False

run_lock = threading.Lock()
run_process = None
run_state = {
    'status': 'idle',
    'started_at': None,
    'ended_at': None,
    'return_code': None,
    'logs': [],
    'log_version': 0,
    'summary': {'elapsed': None, 'api_calls': 0, 'downloads': 0},
    'output_path': '',
    'message': '等待启动',
}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 200000).hex()
    return f'{salt}${digest}'


def verify_password(password, stored):
    try:
        salt, expected = stored.split('$', 1)
    except ValueError:
        return False
    return password_hash(password, salt).split('$', 1)[1] == expected


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    TASKS_DIR.mkdir(exist_ok=True)
    with db() as conn:
        conn.executescript(
            '''
            create table if not exists users (
                id integer primary key autoincrement,
                username text unique not null,
                password_hash text not null,
                role text not null default 'user',
                created_at text not null
            );
            create table if not exists accounts (
                id integer primary key autoincrement,
                label text not null,
                auth_token text not null,
                ct0 text not null,
                cookie text not null,
                screen_name text,
                status text not null default 'active',
                last_checked_at text,
                created_at text not null
            );
            create table if not exists tasks (
                id integer primary key autoincrement,
                user_id integer not null,
                account_id integer,
                task_type text not null,
                title text not null,
                config_json text not null,
                status text not null,
                output_dir text not null,
                log_path text not null,
                error text,
                created_at text not null,
                started_at text,
                finished_at text,
                process_id integer
            );
            '''
        )
        existing = conn.execute('select id from users where username = ?', (DEFAULT_ADMIN_USER,)).fetchone()
        if not existing:
            conn.execute(
                'insert into users (username, password_hash, role, created_at) values (?, ?, ?, ?)',
                (DEFAULT_ADMIN_USER, password_hash(DEFAULT_ADMIN_PASSWORD), 'admin', now()),
            )


def current_user(request: Request):
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    with db() as conn:
        return conn.execute('select * from users where id = ?', (user_id,)).fetchone()


def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={'Location': '/login'})
    return user


def require_admin(request: Request):
    user = require_user(request)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail='Admin only')
    return user


def require_api_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail='未登录')
    return user


def require_api_admin(request: Request):
    user = require_api_user(request)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail='需要管理员权限')
    return user


def row_to_dict(row):
    return dict(row) if row else None


def user_payload(user):
    return {'id': user['id'], 'username': user['username'], 'role': user['role']}


def account_payload(account):
    return {
        'id': account['id'],
        'label': account['label'],
        'screen_name': account['screen_name'],
        'status': account['status'],
        'last_checked_at': account['last_checked_at'],
        'created_at': account['created_at'],
    }


def task_payload(task, include_config=False, include_log=False, include_files=False):
    payload = {
        'id': task['id'],
        'user_id': task['user_id'],
        'username': task['username'] if 'username' in task.keys() else None,
        'account_id': task['account_id'],
        'task_type': task['task_type'],
        'title': task['title'],
        'status': task['status'],
        'error': task['error'],
        'created_at': task['created_at'],
        'started_at': task['started_at'],
        'finished_at': task['finished_at'],
        'process_id': task['process_id'],
    }
    if include_config:
        try:
            payload['config'] = json.loads(task['config_json'])
        except Exception:
            payload['config'] = {}
    if include_log:
        payload['log'] = read_log(task['log_path'])
    if include_files:
        payload['files'] = task_files(task)
    return payload


def task_files(task):
    output_dir = Path(task['output_dir'])
    files = []
    if output_dir.exists():
        for path in sorted(output_dir.rglob('*')):
            if path.is_file() and path.name not in {'account_session.json'}:
                files.append({'name': str(path.relative_to(output_dir)), 'size': path.stat().st_size})
    return files


def task_status_class(status):
    return {
        'queued': 'muted',
        'running': 'active',
        'completed': 'success',
        'failed': 'danger',
        'cancelled': 'danger',
        'rate_limited': 'warning',
        'auth_expired': 'warning',
    }.get(status, 'muted')


templates.env.globals['status_class'] = task_status_class


def read_log(path, max_chars=12000):
    if not path or not os.path.exists(path):
        return ''
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        data = f.read()
    return data[-max_chars:]


def parse_run_summary(line):
    elapsed = re.search(r'共耗时:([0-9.]+)秒', line)
    api_calls = re.search(r'共调用(\d+)次API', line)
    downloads = re.search(r'共下载(\d+)份图片/视频', line)
    if elapsed:
        run_state['summary']['elapsed'] = round(float(elapsed.group(1)), 2)
    if api_calls:
        run_state['summary']['api_calls'] = int(api_calls.group(1))
    if downloads:
        run_state['summary']['downloads'] = int(downloads.group(1))


def append_run_log(line):
    line = line.rstrip()
    if not line:
        return
    run_state['logs'].append(line)
    if len(run_state['logs']) > 250:
        run_state['logs'] = run_state['logs'][-250:]
    run_state['log_version'] += 1
    parse_run_summary(line)


def run_snapshot():
    started_at = run_state['started_at']
    ended_at = run_state['ended_at'] or time.time()
    running_for = round(ended_at - started_at, 2) if started_at else None
    return {
        'status': run_state['status'],
        'started_at': run_state['started_at'],
        'ended_at': run_state['ended_at'],
        'running_for': running_for,
        'return_code': run_state['return_code'],
        'summary': run_state['summary'],
        'output_path': run_state['output_path'],
        'message': run_state['message'],
        'log_version': run_state['log_version'],
        'logs': list(run_state['logs']),
    }


def active_accounts():
    with db() as conn:
        return conn.execute("select * from accounts where status = 'active' order by id desc").fetchall()


def build_runtime_settings(config: dict):
    base = {}
    settings_path = BASE_DIR / 'settings.json'
    if settings_path.exists():
        with open(settings_path, 'r', encoding='utf-8') as f:
            base = json.load(f)
    data = dict(base)
    incoming = dict(config)
    if 'user_lst' in incoming and isinstance(incoming['user_lst'], str):
        incoming['user_lst'] = ','.join(user.strip().lstrip('@') for user in incoming['user_lst'].split(',') if user.strip())
    data.update(incoming)
    data['log_output'] = True
    return data


def start_main_process(config: dict):
    global run_process
    with run_lock:
        if run_process and run_process.poll() is None:
            raise HTTPException(status_code=409, detail='已有任务正在运行，请先停止或等待完成。')

        output_path = (config.get('save_path') or '').strip() or str(BASE_DIR)
        run_state['status'] = 'starting'
        run_state['started_at'] = time.time()
        run_state['ended_at'] = None
        run_state['return_code'] = None
        run_state['logs'] = []
        run_state['log_version'] = 0
        run_state['summary'] = {'elapsed': None, 'api_calls': 0, 'downloads': 0}
        run_state['output_path'] = output_path
        run_state['message'] = '正在启动下载任务'

    runtime_dir = BASE_DIR / '.panel' / 'runtime'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    active_settings = runtime_dir / 'settings.active.json'
    runtime_settings = build_runtime_settings(config)
    with open(active_settings, 'w', encoding='utf-8') as f:
        json.dump(runtime_settings, f, ensure_ascii=False, indent=4)

    python_exe = BASE_DIR / '.venv' / 'Scripts' / 'python.exe'
    if not python_exe.exists():
        python_exe = Path(sys.executable)

    env = os.environ.copy()
    env['TWITTER_DOWNLOAD_SETTINGS'] = str(active_settings)
    env['PYTHONIOENCODING'] = 'utf-8'

    process = subprocess.Popen(
        [str(python_exe), 'main.py'],
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
    )

    def monitor():
        assert process.stdout is not None
        for line in process.stdout:
            append_run_log(line)
        return_code = process.wait()
        with run_lock:
            run_state['return_code'] = return_code
            run_state['ended_at'] = time.time()
            if run_state['status'] == 'stopping':
                run_state['status'] = 'stopped'
                run_state['message'] = '任务已停止'
            elif return_code == 0:
                run_state['status'] = 'finished'
                run_state['message'] = '任务已完成'
            else:
                run_state['status'] = 'failed'
                run_state['message'] = f'任务异常退出，退出码 {return_code}'

    with run_lock:
        run_process = process
        run_state['status'] = 'running'
        run_state['message'] = '任务运行中'

    Thread(target=monitor, daemon=True).start()
    return run_snapshot()


def stop_main_process():
    with run_lock:
        process = run_process
        if not process or process.poll() is not None:
            run_state['status'] = 'idle'
            run_state['message'] = '当前没有运行中的任务'
            return run_snapshot()
        run_state['status'] = 'stopping'
        run_state['message'] = '正在停止任务'

    try:
        if os.name == 'nt':
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
    except Exception:
        process.terminate()

    def force_stop_later():
        time.sleep(5)
        if process.poll() is None:
            process.terminate()

    Thread(target=force_stop_later, daemon=True).start()
    return run_snapshot()


def extract_ct0(cookie):
    for part in cookie.split(';'):
        part = part.strip()
        if part.startswith('ct0='):
            return part.split('=', 1)[1]
    return ''


def validate_account_cookie(cookie):
    ct0 = extract_ct0(cookie)
    if not ct0:
        return False, None, '缺少 ct0'
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
        'cookie': cookie,
        'x-csrf-token': ct0,
    }
    try:
        r = httpx.get('https://x.com/i/api/1.1/account/settings.json', headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return True, data.get('screen_name'), ''
        return False, None, f'HTTP {r.status_code}: {r.text[:200]}'
    except Exception as exc:
        return False, None, str(exc)


def save_account(label, auth_token, ct0, screen_name=None):
    cookie = f'auth_token={auth_token}; ct0={ct0};'
    with db() as conn:
        conn.execute(
            '''
            insert into accounts (label, auth_token, ct0, cookie, screen_name, status, last_checked_at, created_at)
            values (?, ?, ?, ?, ?, 'active', ?, ?)
            ''',
            (label or screen_name or 'X Account', auth_token, ct0, cookie, screen_name, now(), now()),
        )


def start_background_worker():
    global worker_thread
    with worker_lock:
        if worker_thread and worker_thread.is_alive():
            return
        worker_thread = threading.Thread(target=worker_loop, daemon=True)
        worker_thread.start()


def classify_failure(log_text, return_code):
    lower = log_text.lower()
    if 'rate limit exceeded' in lower or 'api次数已超限' in log_text:
        return 'rate_limited', 'X API 次数已超限'
    if 'auth' in lower or 'ct0' in lower or '401' in lower or '403' in lower:
        return 'auth_expired', 'X 会话可能失效'
    return 'failed', f'任务失败, 退出码 {return_code}'


def worker_loop():
    while not stop_worker:
        with db() as conn:
            task = conn.execute("select * from tasks where status = 'queued' order by id asc limit 1").fetchone()
        if not task:
            time.sleep(1)
            continue
        run_task(row_to_dict(task))


def run_task(task):
    output_dir = Path(task['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(task['log_path'])
    config_path = output_dir / 'task_config.json'
    account_path = output_dir / 'account_session.json'

    with db() as conn:
        account = conn.execute('select * from accounts where id = ?', (task['account_id'],)).fetchone()
    if not account:
        with db() as conn:
            conn.execute(
                "update tasks set status = 'auth_expired', error = ?, finished_at = ? where id = ?",
                ('未找到可用 X 账号', now(), task['id']),
            )
        return

    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(task['config_json'])
    with open(account_path, 'w', encoding='utf-8') as f:
        json.dump(
            {
                'auth_token': account['auth_token'],
                'ct0': account['ct0'],
                'cookie': account['cookie'],
            },
            f,
            ensure_ascii=False,
        )

    cmd = [
        sys.executable,
        str(BASE_DIR / 'web_runner.py'),
        '--config',
        str(config_path),
        '--account',
        str(account_path),
        '--output',
        str(output_dir),
    ]
    with open(log_path, 'a', encoding='utf-8', errors='replace') as log_file:
        log_file.write(f'[{now()}] 启动任务 #{task["id"]}: {task["title"]}\n')
        log_file.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        with db() as conn:
            conn.execute(
                "update tasks set status = 'running', started_at = ?, process_id = ? where id = ?",
                (now(), proc.pid, task['id']),
            )
        return_code = proc.wait()
        log_file.write(f'\n[{now()}] 子进程退出码: {return_code}\n')
    log_text = read_log(log_path, 50000)
    if return_code == 0:
        status, error = 'completed', None
    else:
        status, error = classify_failure(log_text, return_code)
    with db() as conn:
        conn.execute(
            'update tasks set status = ?, error = ?, finished_at = ?, process_id = null where id = ?',
            (status, error, now(), task['id']),
        )


@app.on_event('startup')
def on_startup():
    init_db()
    start_background_worker()


@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    index_path = BASE_DIR / 'frontend' / 'dist' / 'index.html'
    if index_path.exists():
        return FileResponse(index_path)
    if not current_user(request):
        return RedirectResponse('/login')
    return RedirectResponse('/tasks')


@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse('login.html', {'request': request, 'error': None})


@app.post('/login')
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with db() as conn:
        user = conn.execute('select * from users where username = ?', (username,)).fetchone()
    if not user or not verify_password(password, user['password_hash']):
        return templates.TemplateResponse('login.html', {'request': request, 'error': '用户名或密码错误'}, status_code=401)
    request.session['user_id'] = user['id']
    return RedirectResponse('/tasks', status_code=303)


@app.post('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/login', status_code=303)


@app.get('/tasks', response_class=HTMLResponse)
def tasks(request: Request, user=Depends(require_user)):
    with db() as conn:
        if user['role'] == 'admin':
            rows = conn.execute('select tasks.*, users.username from tasks join users on users.id = tasks.user_id order by tasks.id desc').fetchall()
        else:
            rows = conn.execute(
                'select tasks.*, users.username from tasks join users on users.id = tasks.user_id where user_id = ? order by tasks.id desc',
                (user['id'],),
            ).fetchall()
    return templates.TemplateResponse('tasks.html', {'request': request, 'user': user, 'tasks': rows})


@app.get('/tasks/new', response_class=HTMLResponse)
def new_task_page(request: Request, user=Depends(require_user)):
    accounts = active_accounts()
    return templates.TemplateResponse('task_form.html', {'request': request, 'user': user, 'accounts': accounts, 'error': None})


def build_task_config(form):
    task_type = form.get('task_type')
    config = {
        'task_type': task_type,
        'targets': form.get('targets') or '',
        'time_range': form.get('time_range') or '',
        'max_concurrent_requests': int(form.get('max_concurrent_requests') or 8),
    }
    for name in ['has_retweet', 'high_lights', 'likes', 'has_video', 'down_log', 'auto_sync', 'md_output', 'media_latest', 'text_down', 'media_down']:
        config[name] = form.get(name) == 'on'
    config.update(
        {
            'image_format': form.get('image_format') or 'orig',
            'media_count_limit': int(form.get('media_count_limit') or 350),
            'proxy': form.get('proxy') or '',
            'tag': form.get('tag') or '',
            'advanced_filter': form.get('advanced_filter') or '',
            'down_count': int(form.get('down_count') or 50),
            'min_replies': int(form.get('min_replies') or 1),
            'min_faves': int(form.get('min_faves') or 0),
            'min_retweets': int(form.get('min_retweets') or 0),
            'search_advanced': form.get('search_advanced') or '',
        }
    )
    return config


def title_from_config(config):
    names = {
        'user_media': '用户媒体',
        'search': '搜索/Tag',
        'text': '用户文本',
        'replies': '评论区',
        'profile': '主页资料',
    }
    target = config.get('targets') or config.get('tag') or config.get('advanced_filter') or '未命名目标'
    target = str(target).replace('\r', ' ').replace('\n', ' ')[:80]
    return f'{names.get(config.get("task_type"), config.get("task_type"))} - {target}'


@app.post('/tasks')
async def create_task(request: Request, user=Depends(require_user)):
    form = await request.form()
    accounts = active_accounts()
    account_id = int(form.get('account_id') or 0)
    if not account_id:
        return templates.TemplateResponse('task_form.html', {'request': request, 'user': user, 'accounts': accounts, 'error': '请先选择 X 账号'}, status_code=400)
    config = build_task_config(form)
    task_dir = TASKS_DIR / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    task_dir.mkdir(parents=True, exist_ok=True)
    log_path = task_dir / 'task.log'
    with db() as conn:
        conn.execute(
            '''
            insert into tasks (user_id, account_id, task_type, title, config_json, status, output_dir, log_path, created_at)
            values (?, ?, ?, ?, ?, 'queued', ?, ?, ?)
            ''',
            (
                user['id'],
                account_id,
                config['task_type'],
                title_from_config(config),
                json.dumps(config, ensure_ascii=False),
                str(task_dir),
                str(log_path),
                now(),
            ),
        )
    start_background_worker()
    return RedirectResponse('/tasks', status_code=303)


def get_task_or_404(task_id, user):
    with db() as conn:
        task = conn.execute('select tasks.*, users.username from tasks join users on users.id = tasks.user_id where tasks.id = ?', (task_id,)).fetchone()
    if not task or (user['role'] != 'admin' and task['user_id'] != user['id']):
        raise HTTPException(status_code=404, detail='Task not found')
    return task


@app.get('/tasks/{task_id}', response_class=HTMLResponse)
def task_detail(task_id: int, request: Request, user=Depends(require_user)):
    task = get_task_or_404(task_id, user)
    output_dir = Path(task['output_dir'])
    files = []
    if output_dir.exists():
        for path in sorted(output_dir.rglob('*')):
            if path.is_file() and path.name not in {'account_session.json'}:
                files.append({'name': str(path.relative_to(output_dir)), 'size': path.stat().st_size})
    return templates.TemplateResponse(
        'task_detail.html',
        {'request': request, 'user': user, 'task': task, 'log': read_log(task['log_path']), 'files': files},
    )


@app.post('/tasks/{task_id}/cancel')
def cancel_task(task_id: int, user=Depends(require_user)):
    task = get_task_or_404(task_id, user)
    if task['status'] == 'queued':
        with db() as conn:
            conn.execute("update tasks set status = 'cancelled', finished_at = ?, error = ? where id = ?", (now(), '用户取消', task_id))
    elif task['status'] == 'running' and task['process_id']:
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(task['process_id']), '/T', '/F'], check=False, capture_output=True)
            else:
                os.kill(int(task['process_id']), signal.SIGTERM)
        except Exception:
            pass
        with db() as conn:
            conn.execute("update tasks set status = 'cancelled', finished_at = ?, process_id = null, error = ? where id = ?", (now(), '用户取消', task_id))
    return RedirectResponse(f'/tasks/{task_id}', status_code=303)


@app.get('/tasks/{task_id}/download')
def download_task(task_id: int, user=Depends(require_user)):
    task = get_task_or_404(task_id, user)
    output_dir = Path(task['output_dir'])
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail='Output not found')
    zip_path = output_dir / f'task-{task_id}.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in output_dir.rglob('*'):
            if path.is_file() and path.name != zip_path.name and path.name != 'account_session.json':
                zf.write(path, path.relative_to(output_dir))
    return FileResponse(zip_path, filename=zip_path.name)


@app.get('/accounts', response_class=HTMLResponse)
def accounts_page(request: Request, user=Depends(require_admin)):
    with db() as conn:
        rows = conn.execute('select * from accounts order by id desc').fetchall()
    return templates.TemplateResponse('accounts.html', {'request': request, 'user': user, 'accounts': rows, 'message': None, 'error': None})


@app.post('/accounts/manual')
async def add_account_manual(request: Request, user=Depends(require_admin)):
    form = await request.form()
    label = form.get('label') or 'X Account'
    auth_token = (form.get('auth_token') or '').strip()
    ct0 = (form.get('ct0') or '').strip()
    if not auth_token or not ct0:
        return RedirectResponse('/accounts?error=missing', status_code=303)
    save_account(label, auth_token, ct0)
    return RedirectResponse('/accounts', status_code=303)


@app.post('/accounts/{account_id}/check')
def check_account(account_id: int, user=Depends(require_admin)):
    with db() as conn:
        account = conn.execute('select * from accounts where id = ?', (account_id,)).fetchone()
    if not account:
        raise HTTPException(status_code=404, detail='Account not found')
    ok, screen_name, error = validate_account_cookie(account['cookie'])
    with db() as conn:
        conn.execute(
            'update accounts set status = ?, screen_name = coalesce(?, screen_name), last_checked_at = ? where id = ?',
            ('active' if ok else 'expired', screen_name, now(), account_id),
        )
    return RedirectResponse('/accounts', status_code=303)


@app.post('/accounts/{account_id}/delete')
def delete_account(account_id: int, user=Depends(require_admin)):
    with db() as conn:
        conn.execute('delete from accounts where id = ?', (account_id,))
    return RedirectResponse('/accounts', status_code=303)


@app.post('/accounts/browser-login')
def browser_login(user=Depends(require_admin)):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Playwright 未安装: {exc}')

    profile_dir = DATA_DIR / 'playwright-x-profile'
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(str(profile_dir), headless=False)
        page = browser.new_page()
        page.goto('https://x.com/i/flow/login', wait_until='domcontentloaded')
        deadline = time.time() + 300
        auth_token = ''
        ct0 = ''
        screen_name = None
        while time.time() < deadline:
            cookies = browser.cookies('https://x.com')
            data = {c['name']: c['value'] for c in cookies}
            auth_token = data.get('auth_token', '')
            ct0 = data.get('ct0', '')
            if auth_token and ct0:
                cookie = f'auth_token={auth_token}; ct0={ct0};'
                ok, screen_name, _ = validate_account_cookie(cookie)
                if ok:
                    break
            time.sleep(2)
        browser.close()
    if not auth_token or not ct0:
        raise HTTPException(status_code=408, detail='5 分钟内未完成 X 登录')
    save_account(screen_name or 'Browser Login', auth_token, ct0, screen_name)
    return RedirectResponse('/accounts', status_code=303)


@app.get('/health')
def health():
    return {'ok': True, 'time': now()}


@app.get('/api/run/config')
def api_run_config():
    settings_path = BASE_DIR / 'settings.json'
    settings = {}
    if settings_path.exists():
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    return {
        'save_path': settings.get('save_path', ''),
        'user_lst': settings.get('user_lst', ''),
        'cookie': '',
        'time_range': settings.get('time_range', '1990-01-01:2030-01-01'),
        'has_retweet': bool(settings.get('has_retweet', False)),
        'high_lights': bool(settings.get('high_lights', False)),
        'likes': bool(settings.get('likes', False)),
        'down_log': bool(settings.get('down_log', False)),
        'autoSync': bool(settings.get('autoSync', False)),
        'image_format': settings.get('image_format', 'orig'),
        'has_video': bool(settings.get('has_video', True)),
        'log_output': True,
        'max_concurrent_requests': int(settings.get('max_concurrent_requests', 8) or 8),
        'proxy': settings.get('proxy', ''),
        'md_output': bool(settings.get('md_output', False)),
        'media_count_limit': int(settings.get('media_count_limit', 350) or 0),
        'project_path': str(BASE_DIR),
    }


@app.get('/api/run/status')
def api_run_status():
    return run_snapshot()


@app.post('/api/run/start')
async def api_run_start(request: Request):
    data = await request.json()
    if 'cookie' not in data or 'auth_token=' not in str(data.get('cookie')) or 'ct0=' not in str(data.get('cookie')):
        raise HTTPException(status_code=400, detail='cookie 必须包含 auth_token 和 ct0。')
    if data.get('image_format') not in {'orig', 'jpg', 'png'}:
        raise HTTPException(status_code=400, detail='image_format 只能是 orig、jpg 或 png。')
    if not re.match(r'^\d{4}-\d{2}-\d{2}:\d{4}-\d{2}-\d{2}$', data.get('time_range', '')):
        raise HTTPException(status_code=400, detail='时间范围格式应为 YYYY-MM-DD:YYYY-MM-DD。')
    users = [user.strip().lstrip('@') for user in str(data.get('user_lst', '')).split(',') if user.strip()]
    if not users:
        raise HTTPException(status_code=400, detail='至少填写一个用户名。')
    return start_main_process(data)


@app.post('/api/run/stop')
def api_run_stop():
    return stop_main_process()


@app.get('/api/run/logs/stream')
async def api_run_logs_stream():
    async def event_generator():
        last_version = -1
        while True:
            snapshot = run_snapshot()
            if snapshot['log_version'] != last_version:
                last_version = snapshot['log_version']
                yield f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.8)

    return StreamingResponse(event_generator(), media_type='text/event-stream')


@app.post('/api/login')
async def api_login(request: Request):
    data = await request.json()
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    with db() as conn:
        user = conn.execute('select * from users where username = ?', (username,)).fetchone()
    if not user or not verify_password(password, user['password_hash']):
        raise HTTPException(status_code=401, detail='用户名或密码错误')
    request.session['user_id'] = user['id']
    return {'user': user_payload(user)}


@app.post('/api/logout')
def api_logout(request: Request):
    request.session.clear()
    return {'ok': True}


@app.get('/api/me')
def api_me(user=Depends(require_api_user)):
    return {'user': user_payload(user)}


@app.get('/api/tasks')
def api_tasks(user=Depends(require_api_user)):
    with db() as conn:
        if user['role'] == 'admin':
            rows = conn.execute('select tasks.*, users.username from tasks join users on users.id = tasks.user_id order by tasks.id desc').fetchall()
        else:
            rows = conn.execute(
                'select tasks.*, users.username from tasks join users on users.id = tasks.user_id where user_id = ? order by tasks.id desc',
                (user['id'],),
            ).fetchall()
    return {'tasks': [task_payload(row) for row in rows]}


@app.post('/api/tasks')
async def api_create_task(request: Request, user=Depends(require_api_user)):
    data = await request.json()
    account_id = int(data.get('account_id') or 0)
    if not account_id:
        raise HTTPException(status_code=400, detail='请先选择 X 账号')
    with db() as conn:
        account = conn.execute("select id from accounts where id = ? and status = 'active'", (account_id,)).fetchone()
    if not account:
        raise HTTPException(status_code=400, detail='X 账号不可用')
    config = {
        'task_type': data.get('task_type'),
        'targets': data.get('targets') or '',
        'time_range': data.get('time_range') or '',
        'max_concurrent_requests': int(data.get('max_concurrent_requests') or 8),
    }
    for name in ['has_retweet', 'high_lights', 'likes', 'has_video', 'down_log', 'auto_sync', 'md_output', 'media_latest', 'text_down', 'media_down']:
        config[name] = bool(data.get(name))
    config.update(
        {
            'image_format': data.get('image_format') or 'orig',
            'media_count_limit': int(data.get('media_count_limit') or 350),
            'proxy': data.get('proxy') or '',
            'tag': data.get('tag') or '',
            'advanced_filter': data.get('advanced_filter') or '',
            'down_count': int(data.get('down_count') or 50),
            'min_replies': int(data.get('min_replies') or 1),
            'min_faves': int(data.get('min_faves') or 0),
            'min_retweets': int(data.get('min_retweets') or 0),
            'search_advanced': data.get('search_advanced') or '',
        }
    )
    if config['task_type'] not in {'user_media', 'search', 'text', 'replies', 'profile'}:
        raise HTTPException(status_code=400, detail='未知任务类型')
    task_dir = TASKS_DIR / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    task_dir.mkdir(parents=True, exist_ok=True)
    log_path = task_dir / 'task.log'
    with db() as conn:
        cursor = conn.execute(
            '''
            insert into tasks (user_id, account_id, task_type, title, config_json, status, output_dir, log_path, created_at)
            values (?, ?, ?, ?, ?, 'queued', ?, ?, ?)
            ''',
            (
                user['id'],
                account_id,
                config['task_type'],
                title_from_config(config),
                json.dumps(config, ensure_ascii=False),
                str(task_dir),
                str(log_path),
                now(),
            ),
        )
        task_id = cursor.lastrowid
    start_background_worker()
    with db() as conn:
        task = conn.execute('select tasks.*, users.username from tasks join users on users.id = tasks.user_id where tasks.id = ?', (task_id,)).fetchone()
    return {'task': task_payload(task, include_config=True)}


@app.get('/api/tasks/{task_id}')
def api_task_detail(task_id: int, user=Depends(require_api_user)):
    task = get_task_or_404(task_id, user)
    return {'task': task_payload(task, include_config=True, include_log=True, include_files=True)}


@app.get('/api/tasks/{task_id}/files')
def api_task_files(task_id: int, user=Depends(require_api_user)):
    task = get_task_or_404(task_id, user)
    return {'files': task_files(task)}


@app.post('/api/tasks/{task_id}/cancel')
def api_cancel_task(task_id: int, user=Depends(require_api_user)):
    task = get_task_or_404(task_id, user)
    if task['status'] == 'queued':
        with db() as conn:
            conn.execute("update tasks set status = 'cancelled', finished_at = ?, error = ? where id = ?", (now(), '用户取消', task_id))
    elif task['status'] == 'running' and task['process_id']:
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(task['process_id']), '/T', '/F'], check=False, capture_output=True)
            else:
                os.kill(int(task['process_id']), signal.SIGTERM)
        except Exception:
            pass
        with db() as conn:
            conn.execute("update tasks set status = 'cancelled', finished_at = ?, process_id = null, error = ? where id = ?", (now(), '用户取消', task_id))
    with db() as conn:
        refreshed = conn.execute('select tasks.*, users.username from tasks join users on users.id = tasks.user_id where tasks.id = ?', (task_id,)).fetchone()
    return {'task': task_payload(refreshed, include_config=True, include_log=True, include_files=True)}


@app.get('/api/accounts')
def api_accounts(user=Depends(require_api_admin)):
    with db() as conn:
        rows = conn.execute('select * from accounts order by id desc').fetchall()
    return {'accounts': [account_payload(row) for row in rows]}


@app.post('/api/accounts/manual')
async def api_add_account_manual(request: Request, user=Depends(require_api_admin)):
    data = await request.json()
    label = data.get('label') or 'X Account'
    auth_token = (data.get('auth_token') or '').strip()
    ct0 = (data.get('ct0') or '').strip()
    if not auth_token or not ct0:
        raise HTTPException(status_code=400, detail='auth_token 和 ct0 都必填')
    save_account(label, auth_token, ct0)
    return {'ok': True}


@app.post('/api/accounts/browser-login')
def api_browser_login(user=Depends(require_api_admin)):
    browser_login(user)
    return {'ok': True}


@app.post('/api/accounts/{account_id}/check')
def api_check_account(account_id: int, user=Depends(require_api_admin)):
    with db() as conn:
        account = conn.execute('select * from accounts where id = ?', (account_id,)).fetchone()
    if not account:
        raise HTTPException(status_code=404, detail='Account not found')
    ok, screen_name, error = validate_account_cookie(account['cookie'])
    with db() as conn:
        conn.execute(
            'update accounts set status = ?, screen_name = coalesce(?, screen_name), last_checked_at = ? where id = ?',
            ('active' if ok else 'expired', screen_name, now(), account_id),
        )
        refreshed = conn.execute('select * from accounts where id = ?', (account_id,)).fetchone()
    return {'account': account_payload(refreshed), 'ok': ok, 'error': error}


@app.delete('/api/accounts/{account_id}')
def api_delete_account(account_id: int, user=Depends(require_api_admin)):
    with db() as conn:
        conn.execute('delete from accounts where id = ?', (account_id,))
    return {'ok': True}


@app.get('/{full_path:path}', response_class=HTMLResponse)
def spa_fallback(full_path: str, request: Request):
    dist = BASE_DIR / 'frontend' / 'dist'
    index_path = dist / 'index.html'
    if full_path.startswith('api/'):
        raise HTTPException(status_code=404, detail='Not found')
    if index_path.exists():
        return FileResponse(index_path)
    if not current_user(request):
        return RedirectResponse('/login')
    return RedirectResponse('/tasks')


init_db()
