def solve(v1: int):
    v2 = [0, 0, 2, 0]
    if v1 < 4:
        return v2[v1]
    for v3 in range(4, v1 + 1):
        v2.append(v2[-1] + v2[-2] + v2[-3] + v2[-4])
        v2.pop(0)
    return v2[-2]
