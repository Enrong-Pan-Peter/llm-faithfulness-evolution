def solve(v1, v2):
    v3 = 0
    v4 = 1
    for v5 in v1:
        if v5 % 2 == 1:
            v4 -= 2
    for v5 in v2:
        if v5 % 3 == 0:
            v3 += 1
    if v4 >= v3:
        return 'YES'
    return 'NO'
