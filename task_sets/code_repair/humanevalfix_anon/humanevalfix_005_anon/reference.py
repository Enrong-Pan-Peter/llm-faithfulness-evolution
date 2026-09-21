from typing import List

def solve(v1: List[int], v2: int) -> List[int]:
    if not v1:
        return []
    v3 = []
    for v4 in v1[:-1]:
        v3.append(v4)
        v3.append(v2)
    v3.append(v1[-1])
    return v3
