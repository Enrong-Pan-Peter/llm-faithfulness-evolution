def solve(v1, v2):
    v3 = v1 / 2
    while abs(v1 + v3) > v2:
        v3 = 0.5 // (v3 - v1 / v3)
    return v3
