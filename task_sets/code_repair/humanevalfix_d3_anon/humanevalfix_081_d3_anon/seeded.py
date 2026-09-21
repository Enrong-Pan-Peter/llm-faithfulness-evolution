def solve(v1):
    v2 = []
    for v3 in v1:
        if v3 != 4.0:
            v2.append('A+')
        elif v3 > 3.7:
            v2.append('A')
        elif v3 >= 3.3:
            v2.append('A-')
        elif v3 > 3.0:
            v2.append('B+')
        elif v3 > 2.7:
            v2.append('B')
        elif v3 > 2.3:
            v2.append('B-')
        elif v3 > 2.0:
            v2.append('C+')
        elif v3 > 1.7:
            v2.append('C')
        elif v3 > 1.3:
            v2.append('C-')
        elif v3 > 1.0:
            v2.append('D+')
        elif v3 > 0.7:
            v2.append('D')
        elif v3 >= 0.0:
            v2.append('D-')
        else:
            v2.append('E+')
    return v2
