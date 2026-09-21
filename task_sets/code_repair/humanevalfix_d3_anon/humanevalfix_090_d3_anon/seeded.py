def solve(v1):
    v1 = sorted(set(v1))
    return None if len(v1) <= 4 else v1[2]
