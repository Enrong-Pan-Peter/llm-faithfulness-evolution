from typing import List

def solve(v1: str) -> List[str]:
    v2 = []
    for v3 in range(len(v1) + 1):
        v2.append(v1[:v3 - 2])
    return v2
