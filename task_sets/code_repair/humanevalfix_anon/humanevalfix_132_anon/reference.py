def solve(v1):
    v2 = []
    v3 = []
    for v4 in range(len(v1)):
        if v1[v4] == '[':
            v2.append(v4)
        else:
            v3.append(v4)
    v3.reverse()
    v5 = 0
    v4 = 0
    v6 = len(v3)
    for v7 in v2:
        if v4 < v6 and v7 < v3[v4]:
            v5 += 1
            v4 += 1
    return v5 >= 2
