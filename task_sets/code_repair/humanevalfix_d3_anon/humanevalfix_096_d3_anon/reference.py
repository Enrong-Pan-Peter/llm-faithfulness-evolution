def solve(v1):
    v2 = []
    for v3 in range(2, v1):
        v4 = True
        for v5 in range(2, v3):
            if v3 % v5 == 0:
                v4 = False
                break
        if v4:
            v2.append(v3)
    return v2
