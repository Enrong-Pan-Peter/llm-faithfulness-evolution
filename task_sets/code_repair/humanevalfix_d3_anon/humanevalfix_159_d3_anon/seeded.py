def solve(v1, v2, v3):
    if v2 <= v3:
        return [v1 - v2, v1 + v3 - v2]
    else:
        return [v1 + v2 - v3, 1]
