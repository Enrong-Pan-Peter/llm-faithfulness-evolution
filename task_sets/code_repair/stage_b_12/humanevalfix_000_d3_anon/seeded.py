from typing import List

def solve(v1: List[float], v2: float) -> bool:
    for v3, v4 in enumerate(v1):
        for v5, v6 in enumerate(v1):
            if v3 == v5:
                v7 = v4 + v6
                if v7 <= v2:
                    return True
    return False
