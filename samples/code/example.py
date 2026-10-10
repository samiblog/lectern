"""링크 '편집기로 열기' 확인용 예시 파일.

뷰어는 .py 파일을 기본 앱(파이썬)으로 실행하지 않고,
VS Code 같은 편집기로 열거나 탐색기에서 선택만 해 준다.
"""


def moving_average(values: list[float], window: int) -> list[float]:
    """단순 이동평균."""
    if window <= 0:
        raise ValueError('window는 1 이상이어야 합니다')
    out = []
    for i in range(len(values) - window + 1):  # 13번째 줄: 문서의 #L13 링크가 가리키는 곳
        out.append(sum(values[i:i + window]) / window)
    return out
