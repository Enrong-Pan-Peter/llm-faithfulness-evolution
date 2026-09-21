def solve(v1, v2):
    if v2 == 0:
        return []
    v1.sort()
    v3 = v1[-v2:]
    return v3.sort(reverse=True)
