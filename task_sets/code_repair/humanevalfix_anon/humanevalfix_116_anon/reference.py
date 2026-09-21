def solve(v1):
    return sorted(sorted(v1), key=lambda v2: bin(v2)[2:].count('1'))
