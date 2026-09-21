def solve(v1):
    return sum([v2 ** 2 for v2 in v1 if v2 > 0 and '.' not in str(v2)])
