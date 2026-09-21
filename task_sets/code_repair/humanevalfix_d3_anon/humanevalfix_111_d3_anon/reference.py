def solve(v1):
    v2 = {}
    v3 = v1.split(' ')
    v4 = 0
    for v5 in v3:
        if v3.count(v5) > v4 and v5 != '':
            v4 = v3.count(v5)
    if v4 > 0:
        for v5 in v3:
            if v3.count(v5) == v4:
                v2[v5] = v4
    return v2
