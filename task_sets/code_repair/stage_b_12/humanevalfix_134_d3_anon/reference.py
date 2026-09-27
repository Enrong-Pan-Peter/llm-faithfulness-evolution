def solve(v1):
    v2 = v1.split(' ')[-1]
    return True if len(v2) == 1 and 97 <= ord(v2.lower()) <= 122 else False
