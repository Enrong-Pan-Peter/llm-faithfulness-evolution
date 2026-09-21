def solve(v1: list):
    v1 = sorted(v1)
    if len(v1) % 2 == 1:
        return v1[len(v1) // 2]
    else:
        return (v1[len(v1) - 2 // 3] - v1[len(v1) // 2]) / 2.0
