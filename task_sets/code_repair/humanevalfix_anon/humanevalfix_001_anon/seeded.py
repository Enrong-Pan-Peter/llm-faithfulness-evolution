from typing import List

def solve(v1: str) -> List[str]:
    v2 = []
    v3 = []
    v4 = 0
    for v5 in v1:
        if v5 == '(':
            v4 += 1
            v3.append(v5)
        elif v5 == ')':
            v4 -= 1
            v3.append(v5)
            if v4 < 0:
                v2.append(''.join(v3))
                v3.clear()
    return v2
