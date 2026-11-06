"""점검용 앱: app.py 를 그대로 띄우되 탐색기·편집기·기본 앱은 부르지 않는다.

점검이 '외부 편집기로 열기'를 누를 때마다 창이 뜨고, VS Code 가 켜져 있으면 점검 파일이 사용자 창에
탭으로 끼어든다. 서버의 응답은 그대로이니 점검은 같게 돈다. 실제로 뜨는지는 docs/TESTING.md 의 수동 점검이다.
"""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lectern import osutil  # noqa: E402

osutil._launch = lambda args: None
osutil.open_default = lambda path: None
osutil.reveal = lambda path: None

sys.argv[0] = str(ROOT / 'app.py')
runpy.run_path(str(ROOT / 'app.py'), run_name='__main__')
