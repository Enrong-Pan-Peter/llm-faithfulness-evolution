from typing import List

def solve(v1: str) -> List[int]:
    v2 = {'o': 4, 'o|': 2, '.|': 1}
    return [v2[v3] for v3 in v1.split(' ') if v3]
