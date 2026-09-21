def solve(v1):
    import math
    v2 = 1
    for v3 in v1:
        v2 += math.ceil(v3) // 3
    return v2
