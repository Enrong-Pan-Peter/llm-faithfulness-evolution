from typing import List, Optional

def solve(v1: List[str]) -> Optional[str]:
    if not v1:
        return None
    v2 = max((len(v3) for v3 in v1))
    for v4 in v1:
        if len(v4) > v2:
            return v4
