"""Integration tests: disposable SQLite data and a local ephemeral HTTP server only."""
import base64
import hashlib
import http.client
import json
import secrets
import tempfile
import threading
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlencode
from server import AuthServer, BASE, AUTH, COOKIE, NONCE, REMEMBER, safe_next

ORIGIN = 'https://labels.example.test'


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / 'sessions.sqlite'
        salt = secrets.token_bytes(16)
        self.password = 'Disposable-test-password-42'
        self.credential = {'username': 'tester', 'iterations': 1000,
                           'salt': base64.b64encode(salt).decode(),
                           'digest': base64.b64encode(hashlib.pbkdf2_hmac('sha256', self.password.encode(), salt, 1000)).decode()}
        self.start()

    def start(self):
        self.server = AuthServer(('127.0.0.1', 0), self.credential, self.database, ORIGIN)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def tearDown(self):
        self.stop()
        self.temp.cleanup()

    def request(self, path, data=None, cookies='', origin=ORIGIN):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        headers = {'Cookie': cookies, 'Origin': origin}
        if data is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            body = urlencode(data)
        else:
            body = None
        conn.request('POST' if data is not None else 'GET', path, body=body, headers=headers)
        r = conn.getresponse()
        result = (r.status, r.getheaders(), r.read().decode())
        conn.close()
        return result

    def nonce(self):
        code, headers, body = self.request(AUTH + 'login')
        self.assertEqual(code, 200)
        self.assertEqual(dict(headers)['Referrer-Policy'], 'same-origin')
        c = SimpleCookie(dict(headers)['Set-Cookie'])
        value = c[NONCE].value
        self.assertIn(value, body)
        return value

    def login(self, remember=True, password=None, destination=BASE):
        nonce = self.nonce()
        form = {'username': 'tester', 'password': self.password if password is None else password,
                'csrf': nonce, 'next': destination}
        if remember:
            form['remember'] = 'yes'
        return self.request(AUTH + 'login', form, f'{NONCE}={nonce}')

    def session_cookie(self, result):
        for k, v in result[1]:
            if k.lower() == 'set-cookie' and v.startswith(COOKIE + '='):
                c = SimpleCookie(v)
                return f'{COOKIE}={c[COOKIE].value}', c[COOKIE]
        self.fail('Session cookie missing')

    def test_anonymous_is_redirected_without_browser_auth_challenge(self):
        code, headers, _ = self.request(AUTH + 'verify')
        self.assertEqual(code, 302)
        self.assertTrue(dict(headers)['Location'].startswith(AUTH + 'login'))
        self.assertNotIn('WWW-Authenticate', dict(headers))

    def test_remember_cookie_and_durable_session(self):
        result = self.login()
        self.assertEqual(result[0], 303)
        cookie, morsel = self.session_cookie(result)
        self.assertEqual(morsel['max-age'], str(REMEMBER))
        self.assertTrue(morsel['secure'])
        self.assertTrue(morsel['httponly'])
        self.assertEqual(morsel['samesite'], 'Lax')
        self.assertEqual(morsel['path'], BASE)
        self.assertEqual(self.request(AUTH + 'verify', cookies=cookie)[0], 204)
        token = morsel.value
        with self.server.db() as db:
            stored = db.execute('SELECT token FROM sessions').fetchone()[0]
        self.assertNotEqual(stored, token)
        self.stop()
        self.start()
        self.assertEqual(self.request(AUTH + 'verify', cookies=cookie)[0], 204)

    def test_nonremembered_cookie_has_no_persistent_lifetime(self):
        _, c = self.session_cookie(self.login(remember=False))
        self.assertEqual(c['max-age'], '')
        self.assertEqual(c['expires'], '')

    def test_bad_password_and_unicode_username_rejected(self):
        self.assertEqual(self.login(password='wrong')[0], 401)
        nonce = self.nonce()
        r = self.request(AUTH + 'login', {'username': '错误账号', 'password': self.password, 'csrf': nonce}, f'{NONCE}={nonce}')
        self.assertEqual(r[0], 401)

    def test_csrf_origin_and_logout_replay(self):
        nonce = self.nonce()
        form = {'username': 'tester', 'password': self.password, 'csrf': nonce}
        self.assertEqual(self.request(AUTH + 'login', form)[0], 403)
        self.assertEqual(self.request(AUTH + 'login', form, f'{NONCE}={nonce}', 'https://evil.test')[0], 403)
        cookie, morsel = self.session_cookie(self.login())
        self.assertEqual(self.request(AUTH + 'logout', {'csrf': 'wrong'}, cookie)[0], 403)
        csrf = hashlib.sha256(('logout:' + morsel.value).encode()).hexdigest()
        r = self.request(AUTH + 'logout', {'csrf': csrf}, cookie)
        self.assertEqual(r[0], 303)
        self.assertIn('Max-Age=0', dict(r[1])['Set-Cookie'])
        self.assertEqual(self.request(AUTH + 'verify', cookies=cookie)[0], 302)

    def test_expired_session_and_changed_credential_invalidated(self):
        cookie, _ = self.session_cookie(self.login())
        with self.server.db() as db:
            db.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.request(AUTH + 'verify', cookies=cookie)[0], 302)
        cookie, _ = self.session_cookie(self.login())
        self.server.fingerprint = 'new-credential'
        self.assertEqual(self.request(AUTH + 'verify', cookies=cookie)[0], 302)

    def test_login_rate_limit(self):
        for _ in range(8):
            self.assertEqual(self.login(password='wrong')[0], 401)
        self.assertEqual(self.login()[0], 429)

    def test_redirects_cannot_leave_app(self):
        for v in ('https://evil.test', '//evil.test', '/other', '/qianshu/../other', '/qianshu/auth/login', '/qianshu/\\evil', 'http://[', '/qianshu/%0d%0aevil'):
            self.assertEqual(safe_next(v), BASE)
        self.assertEqual(dict(self.login(destination='https://evil.test')[1])['Location'], BASE)
        self.assertEqual(safe_next('/qianshu/?x=1'), '/qianshu/?x=1')


if __name__ == '__main__':
    unittest.main()
