from __future__ import annotations

import pytest

from app import DEFAULT_WINDOW, MIN_WINDOW, window_size


@pytest.mark.parametrize('saved, expected', [
    ({'width': 1500, 'height': 900}, (1500, 900)),
    ({'width': '1500', 'height': 900}, (1500, 900)),
    ({'width': 160, 'height': 28}, MIN_WINDOW),              # 최소화한 채 저장된 크기
    (None, DEFAULT_WINDOW),                                  # 손으로 고친 설정이 이상한 경우
    ({'width': 'wide'}, DEFAULT_WINDOW),
    ([1280, 860], DEFAULT_WINDOW),
])
def test_window_size(saved, expected):
    assert window_size(saved) == expected
