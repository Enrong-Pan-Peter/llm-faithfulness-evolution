def solve(v1, v2, v3):
    if v1 == 1:
        return v3
    for v4 in range(2, v1):
        if v1 % v4 == 0:
            return v3
            break
    else:
        return v2
