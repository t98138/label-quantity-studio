"""Generate a private credential file from an existing account password."""
import argparse
import base64
import getpass
import hashlib
import json
import os
import secrets

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', help='Private file outside the static site and Git checkout')
    args = parser.parse_args()
    username = input('用户名: ').strip()
    if not username:
        raise SystemExit('用户名不能为空')
    password = getpass.getpass('现有网站密码: ')
    if not password:
        raise SystemExit('密码不能为空')
    salt = secrets.token_bytes(16)
    data = {'username': username, 'iterations': 600000, 'salt': base64.b64encode(salt).decode(),
            'digest': base64.b64encode(hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)).decode()}
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream)
    print('已生成私有凭据文件；现有文件不会被覆盖。')
