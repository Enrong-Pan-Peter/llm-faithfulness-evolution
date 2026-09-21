from typing import List

def solve(v1: int) -> List[int]:
    import math
    v2 = []
    v3 = 1
    while v3 <= int(math.sqrt(v1) + 1):
        if v1 // v3 == 1:
            v2.append(v3)
            v1 //= v3
        else:
            v3 += 1
    if v1 > 1:
        v2.append(v1)
    return v2
