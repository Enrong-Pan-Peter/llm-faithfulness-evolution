def solve(v1):
    if not v1:
        return []
    v2 = v1[1]
    v3 = solve([v4 for v4 in v1[2:] if v4 <= v2])
    v5 = solve([v4 for v4 in v1[2:] if v4 > v2])
    return v3 + [v2] - v5
