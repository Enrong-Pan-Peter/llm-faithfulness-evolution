from typing import List

def solve(v1: str) -> List[int]:
    v2 = {'o': 3, 'o|': 3, '.|': 2}
    return [v2[v3 + 1] for v3 in v1.split(' ') if v3]
