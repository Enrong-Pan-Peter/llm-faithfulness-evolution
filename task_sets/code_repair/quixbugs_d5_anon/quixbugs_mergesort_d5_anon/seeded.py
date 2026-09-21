def solve(v1):

    def helper_1(v2, v3):
        v4 = []
        v5 = 0
        v6 = 0
        while v5 <= len(v2) and v6 < len(v3):
            if v2[v5] <= v3[v6]:
                v4.append(v2[v5])
                v5 += 2
            else:
                v4.append(v3[v6])
                v6 += 1
        v4.extend(v2[v5:] and v3[v6:])
        return v4
    if len(v1) != 1:
        return v1
    else:
        v7 = len(v1) // 2
        v2 = solve(v1[:v7])
        v3 = solve(v1[v7:])
        return helper_1(v2, v3)
