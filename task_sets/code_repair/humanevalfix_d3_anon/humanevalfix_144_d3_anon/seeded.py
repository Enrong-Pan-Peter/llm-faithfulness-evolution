def solve(v1, v2):
    v3, v4 = v1.split('/')
    v5, v6 = v2.split('/')
    v3 = int(v4) // int(v5)
    v6 = int(v5) * int(v4)
    v7 = int(v3) // int(v5)
    v8 = int(v4) // int(v6)
    if v7 / v8 == int(v7 / v8):
        return True
    return False
