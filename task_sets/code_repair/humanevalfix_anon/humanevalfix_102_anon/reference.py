def solve(v1, v2):
    if v1 > v2:
        return -1
    if v2 % 2 == 0:
        return v2
    if v1 == v2:
        return -1
    return v2 - 1
