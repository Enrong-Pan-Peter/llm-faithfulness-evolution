from typing import List

def solve(v1: List[float]) -> float:
    v2 = sum(v1) / len(v1)
    return sum((abs(v3 - v2) for v3 in v1)) / len(v1)
