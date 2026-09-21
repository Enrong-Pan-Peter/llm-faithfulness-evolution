def solve(v1):
    v2 = 0
    for v3 in v1:
        if v3 > 10:
            v4 = (1, 2, 3, 5, 7, 9)
            v5 = str(v3)
            if int(v5[0]) in v4 and int(v5[-1]) in v4:
                v2 += 1
    return v2
