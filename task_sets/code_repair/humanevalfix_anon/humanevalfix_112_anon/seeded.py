def solve(v1, v2):
    v1 = ''.join([v3 for v3 in v1 if v3 not in v2])
    return (v1, v1[::-1] != v1)
