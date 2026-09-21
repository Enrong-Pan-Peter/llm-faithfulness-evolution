def solve(v1):
    v2 = len(v1) // 2
    v3 = (len(v1) - 1) // 2
    while v2 < len(v1) and v3 >= 0:
        if v1[v2] == 9:
            v1[v2] = 0
            v1[v3] = 0
            v2 += 1
            v3 -= 1
        else:
            v1[v2] += 1
            if v3 != v2:
                v1[v3] += 1
            return v1
    return [1] + (len(v1) - 1) * [0] + [1]
