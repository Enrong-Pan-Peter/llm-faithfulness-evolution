from typing import List

def solve(v1: List[int]) -> List[int]:
    import collections
    v2 = collections.Counter(v1)
    return [v3 for v3 in v1 if v2[v3] <= 1]
