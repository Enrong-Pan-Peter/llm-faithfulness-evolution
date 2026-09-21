def solve(v1):
    return sorted(v1, key=lambda v2: (-len(set(v2)), v2))[0]
