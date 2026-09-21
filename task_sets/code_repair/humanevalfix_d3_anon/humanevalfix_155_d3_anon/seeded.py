def solve(v1):
    v2 = 0
    v3 = 0
    for v4 in str(abs(v1)):
        if int(v4) % 3 != 0:
            v2 += 2
    return (v2, v3)
