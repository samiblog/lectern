"""점검용 앱: app.py 를 그대로 띄우되 탐색기·편집기·기본 앱은 부르지 않는다.

점검이 '외부 편집기로 열기'를 누를 때마다 창이 뜨고, VS Code 가 켜져 있으면 점검 파일이 사용자 창에
탭으로 끼어든다. 서버의 응답은 그대로이니 점검은 같게 돈다. 실제로 뜨는지는 docs/TESTING.md 의 수동 점검이다.
문서 삭제도 사용자의 휴지통 대신 설정 폴더의 test-trash 로 옮긴다. 화면 언어는 Windows 표시 언어와 상관없이 한국어로 둔다.
"""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lectern import i18n, osutil, trash  # noqa: E402

# 점검은 한국어 화면을 본다 — Windows 표시 언어가 영어인 PC(GitHub 러너)에서도 같게 (tests/conftest.py 와 같은 방식).
# 설정 language 를 en 으로 준 점검은 그대로 영어로 뜬다
i18n.system_language = lambda: 'ko'

osutil._launch = lambda args: None
osutil.open_default = lambda path: None
osutil.reveal = lambda path: None


def _test_trash(path: Path) -> None:
    """점검이 사용자의 휴지통을 채우지 않게 설정 폴더 안으로 옮긴다"""
    folder = Path(os.environ.get('LECTERN_CONFIG_DIR', ROOT)) / 'test-trash'
    folder.mkdir(parents=True, exist_ok=True)
    path.replace(folder / path.name)


trash.send = _test_trash

sys.argv[0] = str(ROOT / 'app.py')
runpy.run_path(str(ROOT / 'app.py'), run_name='__main__')
