"""스킬 실행기(skillrun.py — lectern-skill.exe) 시험 (D99)."""
import re
import subprocess
import sys
from pathlib import Path

import skillrun

ROOT = Path(__file__).resolve().parent.parent


def skill(tmp_path, text, name='hello.py'):
    """SKILL.md 가 있는 스킬 폴더에 스크립트를 놓는다."""
    scripts = tmp_path / 'my-skill' / 'scripts'
    scripts.mkdir(parents=True)
    (tmp_path / 'my-skill' / 'SKILL.md').write_text('---\nname: my-skill\n---\n', encoding='utf-8')
    path = scripts / name
    path.write_text(text, encoding='utf-8')
    return path


def run(*args):
    return subprocess.run([sys.executable, str(ROOT / 'skillrun.py'), *map(str, args)],
                          capture_output=True, text=True, encoding='utf-8', timeout=30)


def test_runs_a_skill_script_like_python(tmp_path):
    (path := skill(tmp_path, 'import sys, helper\nprint(helper.WORD, sys.argv[1:], __name__, __file__)\n'))
    (path.parent / 'helper.py').write_text("WORD = 'next-to-script'\n", encoding='utf-8')
    r = run(path, '가 나', '--flag')
    assert r.returncode == 0, r.stderr
    assert "next-to-script ['가 나', '--flag'] __main__" in r.stdout
    assert str(path) in r.stdout


def test_takes_the_flags_scripts_pass_to_their_children(tmp_path):
    path = skill(tmp_path, "print('child')\n")
    assert run('-I', '-B', path).stdout.strip() == 'child'


def test_keeps_the_exit_code(tmp_path):
    path = skill(tmp_path, 'import sys\nsys.exit(7)\n')
    assert run(path).returncode == 7


def test_reports_an_error_like_python(tmp_path):
    """convert.py 가 자식의 까닭을 stderr 마지막 줄에서 읽는다."""
    path = skill(tmp_path, "raise ValueError('까닭입니다')\n")
    r = run(path)
    assert r.returncode == 1
    assert r.stderr.strip().split('\n')[-1] == 'ValueError: 까닭입니다'


def test_runs_only_scripts_of_a_skill(tmp_path):
    loose = tmp_path / 'x.py'
    loose.write_text("print('ran')\n", encoding='utf-8')
    fake = tmp_path / 'scripts'
    fake.mkdir()
    (fake / 'y.py').write_text("print('ran')\n", encoding='utf-8')
    for args in ([loose], [fake / 'y.py'], ['-c', "print('ran')"], ['-m', 'json.tool']):
        r = run(*args)
        assert r.returncode == 2 and 'ran' not in r.stdout, args
        assert '돌리지 않습니다' in r.stderr
    assert run().returncode == 2


def test_refuses_a_missing_or_other_file(tmp_path):
    path = skill(tmp_path, '', 'note.txt')
    assert skillrun.skill_script(str(path)) is None
    assert skillrun.skill_script(str(path.with_name('none.py'))) is None


def test_real_skill_scripts_are_accepted():
    for path in (ROOT / 'skills').glob('*/scripts/*.py'):
        assert skillrun.skill_script(str(path)) == path.resolve()


def test_skill_scripts_start_children_in_a_way_the_runner_accepts():
    """실행기는 -c·-m 을 받지 않는다. 코드 글자로 넘긴 import 는 빌드가 보지도 못한다."""
    for path in (ROOT / 'skills').glob('*/scripts/*.py'):
        text = path.read_text(encoding='utf-8')
        for call in re.findall(r'\[sys\.executable[^\]]*', text):
            assert "'-c'" not in call and "'-m'" not in call, (path.name, call)
        assert '__import__(' not in text and 'importlib' not in text, f'{path.name}: 빌드가 모듈을 찾지 못한다'


def test_build_bundles_the_runner_and_stops_without_its_libraries():
    spec = (ROOT / 'lectern.spec').read_text(encoding='utf-8')
    assert "['skillrun.py']" in spec and "name='lectern-skill'" in spec
    assert 'import PIL' in spec and 'import win32com.client' in spec
    assert 'utf8_mode=1' in spec
    assert 'COLLECT(exe, skill_exe,' in spec
    dev = (ROOT / 'requirements-dev.txt').read_text(encoding='utf-8')
    assert re.search(r'^pillow==', dev, re.M) and re.search(r'^pywin32==.*win32', dev, re.M)


def test_skill_guides_name_the_runner_first():
    for name in ('pptx-to-lectern', 'lectern-to-pptx'):
        text = (ROOT / 'skills' / name / 'SKILL.md').read_text(encoding='utf-8')
        assert 'lectern-skill.exe' in text
        assert not re.search(r'^python <이 스킬>', text, re.M), '실행기를 먼저 쓰도록 <실행기> 로 적는다'
