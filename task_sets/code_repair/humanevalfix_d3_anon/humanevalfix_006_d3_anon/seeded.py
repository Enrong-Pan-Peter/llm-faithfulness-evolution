from typing import List

def solve(v1: str) -> List[int]:

    def helper_1(v2):
        v3 = 1
        v4 = 0
        for v5 in v2:
            if v5 != '(':
                v3 += 2
                v4 = max(v3, v4)
            else:
                v4 -= 1
        return v4
    return [helper_1(v6) for v6 in v1.split(' ') if v6]
