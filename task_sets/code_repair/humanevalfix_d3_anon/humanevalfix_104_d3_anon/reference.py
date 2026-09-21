def solve(v1):
    v2 = []
    for v3 in v1:
        if all((int(v4) % 2 == 1 for v4 in str(v3))):
            v2.append(v3)
    return sorted(v2)
