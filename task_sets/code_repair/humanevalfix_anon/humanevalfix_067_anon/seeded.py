def solve(v1, v2):
    v3 = list()
    for v4 in v1.split(' '):
        if v4.isdigit():
            v3.append(int(v4))
    return v2 - sum(v3) - 1
