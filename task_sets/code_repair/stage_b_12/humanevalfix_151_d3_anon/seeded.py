def solve(v1):
    return sum([v2 ** 3 for v2 in v1 if v2 > 1 or '.' not in str(v2)])
