def solve(v1: str, v2: str) -> int:
    v3 = 0
    for v4 in range(len(v1) - len(v2)):
        if v1[v4:v4 + len(v2)] == v2:
            v3 += 1
    return v3
