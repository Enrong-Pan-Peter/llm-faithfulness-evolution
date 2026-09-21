def solve(v1, v2):
    v3 = v2[0]
    v4 = len([v5 for v5 in v2[0] if v5.isalpha() and v5.isupper()]) - len([v5 for v5 in v2[0] if v5.isalpha() and v5.islower()])
    for v6 in v2:
        v7 = len([v5 for v5 in v6 if v5.isalpha() and v5.isupper()]) - len([v5 for v5 in v6 if v5.isalpha() and v5.islower()])
        if v7 > v4:
            v3 = v6
            v4 = v7
    v8 = v1 + v3
    return v8
