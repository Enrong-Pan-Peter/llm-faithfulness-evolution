def solve(v1):
    if v1 == 1:
        return []
    for v2 in range(2, int(v1 ** 0.5) + 1):
        if v1 % v2 == 0:
            return [v2] + solve(v1 // v2)
    return []
