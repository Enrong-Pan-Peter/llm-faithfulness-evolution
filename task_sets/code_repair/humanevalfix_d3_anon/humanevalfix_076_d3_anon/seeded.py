def solve(v1, v2):
    if v2 == 2:
        return v1 != 1
    v3 = 2
    while v2 < v1:
        v3 = v3 * v2
    return v3 == v1
