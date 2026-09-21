def solve(v1):
    v2 = []
    for v3 in range(len(v1)):
        if v3 % 3 == 0:
            v2.append(v1[v3] ** 3)
        elif v3 % 3 != 0:
            v2.append(v1[v3 + 1] ** 3)
        else:
            v2.append(v1[v3])
    return sum(v2)
