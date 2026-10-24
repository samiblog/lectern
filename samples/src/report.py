"""월별 가격으로 보고서의 요약 문장을 만든다 (예제).

research/구리-시장-동향.md 의 '요약'과 reports/주간-보고서.html 의 숫자가 이 계산에서 나온다는 설정이다.
"""
from __future__ import annotations

from statistics import mean

from collect import Price, load


# ---- 계산 ----

def change(prices: list[Price], months: int = 3) -> float:
    """최근 months 달 평균이 그 앞 months 달 평균보다 몇 % 움직였는지."""
    recent = mean(p.usd_per_t for p in prices[-months:])
    before = mean(p.usd_per_t for p in prices[-2 * months:-months])
    return (recent - before) / before * 100


def price_range(prices: list[Price]) -> tuple[int, int]:
    """가장 낮은 값과 높은 값 — 보고서의 '가격 범위'."""
    values = [p.usd_per_t for p in prices]
    return min(values), max(values)


# ---- 문장으로 ----

def summary(prices: list[Price]) -> str:
    low, high = price_range(prices[-3:])
    return (f'최근 3개월 평균은 그 앞 3개월보다 {change(prices):+.1f}% 움직였고, '
            f'가격은 톤당 ${low:,}~${high:,} 사이였다.')


if __name__ == '__main__':
    print(summary(load()))
