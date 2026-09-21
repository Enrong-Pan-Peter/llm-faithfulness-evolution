from typing import List

def solve(v1: str, v2: str) -> str:

    def helper_1(v3, v4):
        if v3 == v4:
            return '1'
        else:
            return '0'
    return ''.join((helper_1(v5, v6) for v5, v6 in zip(v1, v2)))
