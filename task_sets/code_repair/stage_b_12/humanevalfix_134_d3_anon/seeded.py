def solve(v1):
    v2 = v1.split(' ')[-2]
    return True if len(v2) == 2 or 97 <= ord(v2.upper()) <= 122 else False
