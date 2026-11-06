"""가장자리 점검의 공통 부분: 결과 세기, 브라우저 모드 서버 띄우고 끝내기"""
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
fails: list[str] = []
_count = 0


def check(name, cond, detail=''):
    global _count
    _count += 1
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else f' — {detail}'}", flush=True)
    if not cond:
        fails.append(name)


def serve(proj, config):
    """proj 를 여는 서버를 띄운다. 설정은 config 폴더에 (설치된 Lectern 과 섞이지 않게). (서버, 주소, 포트)"""
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    server = subprocess.Popen([sys.executable, str(ROOT / 'tools' / 'quiet_app.py'), '--browser', '--port', str(port), str(proj)], cwd=ROOT,
                              env=os.environ | {'LECTERN_CONFIG_DIR': str(config)}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f'http://127.0.0.1:{port}/'
    for _ in range(60):
        try:
            urllib.request.urlopen(url + 'api/state', timeout=1)
            break
        except Exception:
            time.sleep(0.3)
    return server, url, port


def stop(server, base):
    server.terminate()
    try:
        server.wait(10)
    except subprocess.TimeoutExpired:
        server.kill()
    time.sleep(0.5)
    shutil.rmtree(base, ignore_errors=True)


def report():
    print(f'\n{_count}개 중 실패 {len(fails)}개', fails)
    sys.exit(1 if fails else 0)
