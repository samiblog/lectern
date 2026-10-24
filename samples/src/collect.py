"""구리 월평균 가격을 모아 data/월별-가격.csv 에 덧붙인다 (예제 — 실제로 인터넷에서 받지 않는다).

Lectern 은 이 파일을 실행하지 않는다. '코드' 목록에서 누르면 줄 번호와 언어 색으로 읽기만 하고,
오른쪽 목차에는 아래의 클래스·함수와 '# ---- … ----' 구분 주석이 나온다.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / 'data' / '월별-가격.csv'


# ---- 자료 모양 ----

@dataclass
class Price:
    month: str      # '2026-06'
    usd_per_t: int  # 톤당 달러


# ---- 읽고 모으기 ----

def load(path: Path = DATA) -> list[Price]:
    """지금까지 모은 가격 (파일이 없으면 빈 목록)."""
    if not path.exists():
        return []
    with path.open(encoding='utf-8') as f:
        return [Price(row['월'], int(row['가격'])) for row in csv.DictReader(f)]


def fetch_latest() -> list[Price]:
    """거래소의 최근 월평균 가격. 예제라서 고정 값을 돌려준다."""
    return [Price('2026-05', 10760), Price('2026-06', 11220)]


def merge(old: list[Price], new: list[Price]) -> list[Price]:
    """같은 달은 새 값으로 바꾸고 달 순서로 정렬한다."""
    by_month = {p.month: p for p in old}
    by_month.update({p.month: p for p in new})
    return sorted(by_month.values(), key=lambda p: p.month)


# ---- 저장 ----

def save(prices: list[Price], path: Path = DATA) -> None:
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['월', '가격'])
        for p in prices:
            writer.writerow([p.month, p.usd_per_t])


if __name__ == '__main__':
    save(merge(load(), fetch_latest()))
