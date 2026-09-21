from typing import List, Tuple

def solve(v1: List[int]) -> List[int]:
    v2 = None
    v3 = []
    for v4 in v1:
        if v2 is None:
            v2 = v4
        else:
            v2 = max(v2, v4)
        v3.append(v2)
    return v3
