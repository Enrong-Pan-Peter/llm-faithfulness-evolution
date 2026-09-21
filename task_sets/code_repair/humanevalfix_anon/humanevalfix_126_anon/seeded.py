def solve(v1):
    v2 = dict([(v3, 0) for v3 in v1])
    for v3 in v1:
        v2[v3] += 1
    if all((v1[v3 - 1] <= v1[v3] for v3 in range(1, len(v1)))):
        return True
    else:
        return False
