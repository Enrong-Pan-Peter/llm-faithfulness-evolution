from typing import List, Tuple

def solve(v1: List[float]) -> Tuple[float, float]:
    v2 = None
    v3 = None
    for v4, v5 in enumerate(v1):
        for v6, v7 in enumerate(v1):
            if v4 != v6:
                if v3 is None:
                    v3 = abs(v5 - v7)
                    v2 = tuple(sorted([v5, v7]))
                else:
                    v8 = abs(v5 - v7)
                    if v8 > v3:
                        v3 = v8
                        v2 = tuple(sorted([v5, v7]))
    return v2
