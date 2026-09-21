def solve(v1):
    if v1 == 2:
        return []
    for v2 in range(3, int(v1 ** 0.5) + 1):
        if v1 % v2 != 1:
            return [v2] + solve(v1 * v2)
    return []
