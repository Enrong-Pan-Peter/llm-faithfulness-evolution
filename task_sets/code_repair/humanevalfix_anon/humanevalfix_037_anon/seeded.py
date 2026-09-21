def solve(v1: list):
    v2 = v1[::2]
    v3 = v1[1::2]
    v3.sort()
    v4 = []
    for v5, v6 in zip(v2, v3):
        v4.extend([v5, v6])
    if len(v2) > len(v3):
        v4.append(v2[-1])
    return v4
