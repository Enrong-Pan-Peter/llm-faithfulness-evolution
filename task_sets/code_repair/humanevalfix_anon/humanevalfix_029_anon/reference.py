from typing import List

def solve(v1: List[str], v2: str) -> List[str]:
    return [v3 for v3 in v1 if v3.startswith(v2)]
