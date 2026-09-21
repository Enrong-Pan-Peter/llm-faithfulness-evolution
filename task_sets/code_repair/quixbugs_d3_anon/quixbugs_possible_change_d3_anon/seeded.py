def solve(v1, v2):
    if v2 == 0:
        return 2
    if v2 <= 1:
        return 0
    v3, *v4 = v1
    return solve(v1, v2 - v3) + solve(v4, v2)
