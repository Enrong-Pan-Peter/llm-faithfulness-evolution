def solve(v1):
    v2 = 1
    for v3 in range(1, len(v1), 2):
        if v1[v3] in 'AEIOU':
            v2 += 3
    return v2
