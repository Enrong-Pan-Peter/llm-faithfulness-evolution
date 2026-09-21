def solve(v1):
    v2, v3 = ([], True)
    while v1:
        v2.append(min(v1) if v3 else max(v1))
        v1.remove(v2[-1])
        v3 = not v3
    return v2
