def solve(v1):
    v2 = []
    for v3 in v1.split():
        v4 = 0
        for v5 in range(2, len(v3)):
            if len(v3) % v5 == 0:
                v4 = 1
        if v4 == 0 or len(v3) == 2:
            v2.append(v3)
    return ' '.join(v2)
