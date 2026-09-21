def solve(v1, v2, v3):
    return v1 * v1 == v2 * v2 + v3 * v3 or v2 * v2 == v1 * v1 + v3 * v3 or v3 * v3 == v1 * v1 + v2 * v2
