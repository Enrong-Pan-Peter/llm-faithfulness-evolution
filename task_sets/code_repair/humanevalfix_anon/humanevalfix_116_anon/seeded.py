def solve(v1):
    return sorted(sorted(v1), key=lambda v2: v1.count('1'))
