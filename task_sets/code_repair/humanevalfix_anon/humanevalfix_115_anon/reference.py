def solve(v1, v2):
    import math
    return sum([math.ceil(sum(v3) / v2) for v3 in v1])
