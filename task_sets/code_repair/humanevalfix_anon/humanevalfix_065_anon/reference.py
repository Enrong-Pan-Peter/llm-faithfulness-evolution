def solve(v1, v2):
    v3 = str(v1)
    if v2 > len(v3):
        return v3[::-1]
    else:
        return v3[len(v3) - v2:] + v3[:len(v3) - v2]
