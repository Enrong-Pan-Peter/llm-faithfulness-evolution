def solve(v1):
    from math import floor, ceil
    if v1.count('.') == 1:
        while v1[-1] == '0':
            v1 = v1[:-1]
    v2 = float(v1)
    if v1[-2:] == '.5':
        if v2 > 0:
            v3 = floor(v2)
        else:
            v3 = ceil(v2)
    elif len(v1) > 0:
        v3 = int(round(v2))
    else:
        v3 = 0
    return v3
