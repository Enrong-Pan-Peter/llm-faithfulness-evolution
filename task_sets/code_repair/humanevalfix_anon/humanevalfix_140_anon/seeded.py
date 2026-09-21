def solve(v1):
    v2 = ''
    v3 = 0
    v4, v5 = (0, 0)
    while v3 < len(v1):
        if v1[v3] == ' ':
            v5 += 1
        else:
            if v5 - v4 > 2:
                v2 += '-' + v1[v3]
            elif v5 - v4 > 0:
                v2 += '_' * (v5 - v4) + v1[v3]
            else:
                v2 += v1[v3]
            v4, v5 = (v3 + 1, v3 + 1)
        v3 += 1
    if v5 - v4 > 2:
        v2 += '-'
    elif v5 - v4 > 0:
        v2 += '__'
    return v2
