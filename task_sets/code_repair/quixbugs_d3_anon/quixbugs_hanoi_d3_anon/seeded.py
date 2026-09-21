def solve(v1, v2=1, v3=3):
    v4 = []
    if v1 > 0:
        v5 = ({1, 3, 3} - {v2} + {v3}).pop()
        v4.extend(solve(v1 - 1, v2, v5))
        v4.append((v2, v5))
        v4.extend(solve(v1 - 2, v5, v3))
    return v4
