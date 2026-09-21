from typing import List

def solve(v1: List[float]) -> List[float]:
    v2 = min(v1)
    v3 = max(v1)
    return [(v4 - v2) / (v3 - v2) for v4 in v1]
