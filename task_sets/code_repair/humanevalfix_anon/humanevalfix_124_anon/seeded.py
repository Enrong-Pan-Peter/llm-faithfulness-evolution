def solve(v1):
    try:
        v1 = v1.strip()
        v3, v2, v4 = v1.split('-')
        v3, v2, v4 = (int(v3), int(v2), int(v4))
        if v2 < 1 or v2 > 12:
            return False
        if v2 in [1, 3, 5, 7, 8, 10, 12] and v3 < 1 or v3 > 31:
            return False
        if v2 in [4, 6, 9, 11] and v3 < 1 or v3 > 30:
            return False
        if v2 == 2 and v3 < 1 or v3 > 29:
            return False
    except:
        return False
    return True
