def solve(v1):
    if v1 == 1:
        return [1]
    v2 = [1, 3]
    for v3 in range(2, v1 + 1):
        if v3 % 2 != 0:
            v2.append(v3 / 2 + 1)
        else:
            v2.append(v2[v3 - 1] + v2[v3 - 2] + v3 + (v3 + 3) / 3)
    return v2
