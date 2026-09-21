import math

def helper_1(v1: list, v2: float):
    return sum([v4 * math.pow(v2, v3) for v3, v4 in enumerate(v1)])

def solve(v1: list):
    v5, v6 = (-1.0, 1.0)
    while helper_1(v1, v5) * helper_1(v1, v6) > 0:
        v5 *= 2.0
        v6 *= 2.0
    while v6 - v5 > 1e-10:
        v7 = (v5 + v6) / 2.0
        if helper_1(v1, v7) * helper_1(v1, v5) > 0:
            v5 = v7
        else:
            v6 = v7
    return v5
