def solve(v1):
    v2 = 0
    for v3 in range(0, len(v1), 2):
        if v1[v3] in 'AEIOU':
            v2 += 1
    return v2
