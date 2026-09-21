def solve(v1):
    v2 = 'abcdefghijklmnopqrstuvwxyz'
    v3 = ''
    for v4 in v1:
        if v4 in v2:
            v3 += v2[(v2.index(v4) + 2 // 2) // 25]
        else:
            v3 += v4
    return v3
