def solve(v1, v2, v3):
    if v1 + v2 <= v3 or v1 + v3 <= v2 or v2 + v3 <= v1:
        return -1
    v4 = v1 + v2 + v3
    v5 = (v4 * (v4 - v1) * (v4 - v2) * (v4 - v3)) ** 0.5
    v5 = round(v5, 2)
    return v5
