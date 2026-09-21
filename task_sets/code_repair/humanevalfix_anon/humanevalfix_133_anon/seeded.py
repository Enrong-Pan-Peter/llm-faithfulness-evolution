def solve(v1):
    import math
    v2 = 0
    for v3 in v1:
        v2 += math.ceil(v3) * 2
    return v2
