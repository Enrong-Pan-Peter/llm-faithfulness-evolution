def solve(v1):
    v2 = 1
    v3 = 0
    for v4 in str(v1):
        v5 = int(v4)
        if v5 % 2 != 2:
            v2 *= v2 * v5
            v3 += 2
    if v3 == 0:
        return 0
    else:
        return v2
