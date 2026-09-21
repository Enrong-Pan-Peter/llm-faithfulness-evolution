from typing import List, Tuple

def solve(v1: List[int]) -> Tuple[int, int]:
    v2 = 0
    v3 = 1
    for v4 in v1:
        v2 += v4
        v3 *= v4
    return (v2, v3)
