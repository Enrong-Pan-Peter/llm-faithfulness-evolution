def solve(v1: int):
    v2 = []
    for v3 in range(v1):
        if v3 % 11 == 0 or v3 % 13 == 0:
            v2.append(v3)
    v4 = ''.join(list(map(str, v2)))
    v5 = 0
    for v6 in v4:
        v5 += v6 == '7'
    return v5
