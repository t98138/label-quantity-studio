#!/usr/bin/env python3
"""Start the local label app independently of its launching terminal."""
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8767/'
STATE = ROOT / '.work' / 'server'


def running():
    try:
        with urlopen(URL, timeout=1) as response:
            body = response.read(8192).decode('utf-8', errors='replace')
        if '签数 · 标签用量助手' not in body:
            raise RuntimeError('8767端口正被其他网页占用，请先确认对应程序。')
        return True
    except (URLError, TimeoutError, OSError) as exc:
        if isinstance(exc, HTTPError):
            raise RuntimeError('8767端口已有其他服务，请先确认对应程序。') from exc
        return False


def main():
    if running():
        print('签数已在运行：' + URL)
        return
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'server.log').open('ab') as log:
        process = subprocess.Popen(
            [sys.executable, '-u', '-m', 'http.server', '8767', '--bind', '127.0.0.1', '--directory', str(ROOT / 'dist')],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            start_new_session=True, close_fds=True,
        )
    for _ in range(30):
        if process.poll() is not None:
            raise RuntimeError('签数启动失败，请查看 .work/server/server.log。')
        if running():
            (STATE / 'server.pid').write_text(str(process.pid))
            print('签数已启动：' + URL)
            print('关闭启动窗口后仍可访问；电脑重启后请再次双击启动。')
            return
        time.sleep(.1)
    process.terminate()
    raise RuntimeError('服务启动超时，请查看 .work/server/server.log。')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
