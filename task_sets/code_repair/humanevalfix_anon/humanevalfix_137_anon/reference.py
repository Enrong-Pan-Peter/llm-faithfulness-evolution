def solve(v1, v2):
    v3, v4 = (v1, v2)
    if isinstance(v3, str):
        v3 = v3.replace(',', '.')
    if isinstance(v4, str):
        v4 = v4.replace(',', '.')
    if float(v3) == float(v4):
        return None
    return v1 if float(v3) > float(v4) else v2
