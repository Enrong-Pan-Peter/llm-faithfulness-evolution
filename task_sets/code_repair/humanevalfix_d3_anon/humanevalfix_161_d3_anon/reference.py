def solve(v1):
    v2 = 0
    v3 = 0
    v4 = list(v1)
    for v5 in v1:
        if v5.isalpha():
            v4[v3] = v5.swapcase()
            v2 = 1
        v3 += 1
    v1 = ''
    for v5 in v4:
        v1 += v5
    if v2 == 0:
        return v1[len(v1)::-1]
    return v1
