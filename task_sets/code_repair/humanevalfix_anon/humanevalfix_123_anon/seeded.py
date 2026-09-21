def solve(v1):
    if v1 % 2 == 0:
        v2 = []
    else:
        v2 = [v1]
    while v1 > 1:
        if v1 % 2 == 0:
            v1 = v1 / 2
        else:
            v1 = v1 * 2 + 1
        if v1 % 2 == 1:
            v2.append(int(v1))
    return sorted(v2)
