from typing import List

def solve(v1: List[int]) -> bool:
    v2 = 0
    for v3 in v1:
        v2 += v3
        if v2 < 0:
            return True
    return False
