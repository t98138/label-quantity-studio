"""Cookie authentication gateway for Caddy forward_auth; no label data served here."""
import base64
from contextlib import contextmanager
import hashlib
import hmac
import html
import json
import os
import secrets
import sqlite3
import sys
import time
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit, unquote

BASE = '/qianshu/'
AUTH = BASE + 'auth/'
COOKIE = '__Secure-qianshu_session'
NONCE = '__Secure-qianshu_login'
REMEMBER = 90 * 24 * 3600
TEMPORARY = 12 * 3600
MAX_ATTEMPTS = 8
WINDOW = 15 * 60


def safe_next(value):
    """Only permit app-relative destinations, never an external URL or auth loop."""
    if not isinstance(value, str) or len(value) > 2048:
        return BASE
    decoded = unquote(value)
    try:
        parts = urlsplit(decoded)
    except ValueError:
        return BASE
    if (parts.scheme or parts.netloc or not parts.path.startswith(BASE)
            or parts.path.startswith(AUTH) or '\\' in decoded
            or any(ord(c) < 32 for c in decoded) or '..' in parts.path.split('/')):
        return BASE
    return value


class AuthServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, credential, database, origin):
        self.credential = credential
        self.database = str(database)
        self.origin = origin.rstrip('/')
        if urlsplit(self.origin).scheme not in ('https', 'http'):
            raise ValueError('A fixed public origin is required')
        self.fingerprint = hashlib.sha256(json.dumps(credential, sort_keys=True).encode()).hexdigest()
        self.template = Path(__file__).with_name('page.html').read_text()
        with self.db() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, expires INTEGER NOT NULL, version TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS attempts (ip TEXT PRIMARY KEY, start INTEGER NOT NULL, count INTEGER NOT NULL)')
        super().__init__(address, Handler)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def session(self, token):
        if not token or len(token) > 128:
            return None
        with self.db() as db:
            row = db.execute('SELECT expires FROM sessions WHERE token=? AND version=? AND expires>?',
                             (hashlib.sha256(token.encode()).hexdigest(), self.fingerprint, int(time.time()))).fetchone()
        return row

    def attempt(self, ip):
        now = int(time.time())
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM attempts WHERE start<=?', (now - WINDOW,))
            row = db.execute('SELECT count FROM attempts WHERE ip=?', (ip,)).fetchone()
            if row and row[0] >= MAX_ATTEMPTS:
                return False
            db.execute('INSERT INTO attempts VALUES (?,?,1) ON CONFLICT(ip) DO UPDATE SET count=count+1', (ip, now))
        return True


class Handler(BaseHTTPRequestHandler):
    server_version = 'QianshuAuth'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *_):
        # Never log credentials, cookies, or request query strings.
        pass

    def cookie(self, name):
        try:
            c = SimpleCookie(self.headers.get('Cookie', ''))
            return c[name].value if name in c else ''
        except CookieError:
            return ''

    def respond(self, code, body='', cookies=(), location=None):
        data = body.encode()
        self.send_response(code)
        self.send_header('Cache-Control', 'private, no-store')
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        for cookie in cookies:
            self.send_header('Set-Cookie', cookie)
        if location:
            self.send_header('Location', location)
        if code == 429:
            self.send_header('Retry-After', str(WINDOW))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def page(self, content, message='', code=200, cookies=()):
        body = self.server.template.replace('{{content}}', content).replace('{{message}}', html.escape(message))
        self.respond(code, body, cookies)

    def login_page(self, destination=BASE, message='', code=200):
        nonce = secrets.token_urlsafe(32)
        content = '''<form method="post" action="/qianshu/auth/login">
<input type="hidden" name="csrf" value="CSRF"><input type="hidden" name="next" value="NEXT">
<label for="username">账号</label><input id="username" name="username" autocomplete="username" required value="USER" maxlength="128">
<label for="password">密码</label><input id="password" type="password" name="password" autocomplete="current-password" required maxlength="1024">
<label class="remember"><input type="checkbox" name="remember" value="yes" checked><span>记住此设备 <small>90 天内自动登录</small></span></label>
<button type="submit">登录签数 <span aria-hidden="true">↗</span></button>
</form><p class="foot">仅在你自己的设备上勾选。<br>使用完公共设备后，请退出登录。</p>'''
        content = content.replace('CSRF', nonce).replace('NEXT', html.escape(safe_next(destination), quote=True)).replace('USER', html.escape(self.server.credential['username'], quote=True))
        self.page(content, message, code, (f'{NONCE}={nonce}; Path={AUTH}; Secure; HttpOnly; SameSite=Lax; Max-Age=900',))

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url = urlsplit(self.path)
        token = self.cookie(COOKIE)
        session = self.server.session(token)
        if url.path == AUTH + 'verify':
            if session:
                self.respond(204)
            else:
                original = self.headers.get('X-Forwarded-Uri', BASE)
                if not original.startswith(BASE):
                    original = BASE + original.lstrip('/')
                self.respond(302, location=AUTH + 'login?next=' + quote(safe_next(original), safe=''))
        elif url.path == AUTH + 'login':
            destination = safe_next(parse_qs(url.query).get('next', [BASE])[0])
            if session:
                self.respond(303, location=destination)
            else:
                self.login_page(destination)
        elif url.path == AUTH + 'logout':
            if not session:
                self.respond(303, location=AUTH + 'login')
                return
            csrf = hashlib.sha256(('logout:' + token).encode()).hexdigest()
            self.page('<h2>退出此设备？</h2><p class="description">退出后，下次打开需要重新登录。</p>'
                      f'<form method="post" action="{AUTH}logout"><input type="hidden" name="csrf" value="{csrf}">'
                      '<button type="submit">退出登录</button></form>'
                      f'<a class="back" href="{BASE}">继续使用签数 ↗</a>')
        else:
            self.respond(404)

    def do_POST(self):
        path = urlsplit(self.path).path
        # POSTs must originate from the configured HTTPS site, not an arbitrary Host.
        if self.headers.get('Origin') != self.server.origin:
            print('Rejected authentication request: origin does not match configured site', file=sys.stderr, flush=True)
            self.respond(403)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self.respond(400)
            return
        if length <= 0 or length > 8192:
            self.respond(413)
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
            self.respond(415)
            return
        try:
            form = parse_qs(self.rfile.read(length).decode('utf-8'), max_num_fields=8)
        except (ValueError, UnicodeError):
            self.respond(400)
            return
        field = lambda name: form.get(name, [''])[0]
        if path == AUTH + 'login':
            nonce = self.cookie(NONCE)
            if len(nonce) < 32 or not hmac.compare_digest(nonce.encode(), field('csrf').encode()):
                print('Rejected authentication request: login form token missing or stale', file=sys.stderr, flush=True)
                self.respond(403)
                return
            ip = self.headers.get('X-Forwarded-For', self.client_address[0]).split(',')[-1].strip()[:128]
            if not self.server.attempt(ip):
                self.login_page(message='尝试次数较多，请在 15 分钟后重试。', code=429)
                return
            cred = self.server.credential
            digest = hashlib.pbkdf2_hmac('sha256', field('password').encode(), base64.b64decode(cred['salt']), cred['iterations'])
            valid_password = hmac.compare_digest(digest, base64.b64decode(cred['digest']))
            if not (hmac.compare_digest(field('username').encode(), cred['username'].encode()) and valid_password):
                self.login_page(field('next'), '账号或密码不正确，请重试。', 401)
                return
            token = secrets.token_urlsafe(32)
            duration = REMEMBER if field('remember') == 'yes' else TEMPORARY
            now = int(time.time())
            with self.server.db() as db:
                old = self.cookie(COOKIE)
                if old:
                    db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(old.encode()).hexdigest(),))
                db.execute('DELETE FROM sessions WHERE expires<=?', (now,))
                db.execute('DELETE FROM attempts WHERE ip=?', (ip,))
                db.execute('INSERT INTO sessions VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), now + duration, self.server.fingerprint))
            cookie = f'{COOKIE}={token}; Path={BASE}; Secure; HttpOnly; SameSite=Lax'
            if duration == REMEMBER:
                cookie += f'; Max-Age={REMEMBER}'
            self.respond(303, cookies=(cookie, f'{NONCE}=; Path={AUTH}; Secure; HttpOnly; SameSite=Lax; Max-Age=0'), location=safe_next(field('next')))
        elif path == AUTH + 'logout':
            token = self.cookie(COOKIE)
            expected = hashlib.sha256(('logout:' + token).encode()).hexdigest()
            if not token or not hmac.compare_digest(expected.encode(), field('csrf').encode()):
                self.respond(403)
                return
            with self.server.db() as db:
                db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(token.encode()).hexdigest(),))
            self.respond(303, cookies=(f'{COOKIE}=; Path={BASE}; Secure; HttpOnly; SameSite=Lax; Max-Age=0',), location=AUTH + 'login')
        else:
            self.respond(404)


if __name__ == '__main__':
    credential = json.loads(Path(os.environ['QS_CREDENTIAL']).read_text())
    state = Path(os.environ.get('STATE_DIRECTORY', '/var/lib/qianshu-auth'))
    state.mkdir(parents=True, exist_ok=True)
    server = AuthServer((os.environ.get('QS_BIND', '127.0.0.1'), int(os.environ.get('QS_PORT', '8787'))),
                        credential, state / 'sessions.sqlite', os.environ['QS_ORIGIN'])
    server.serve_forever()
