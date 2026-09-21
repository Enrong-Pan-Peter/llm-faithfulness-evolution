def solve(v1):
    if ' ' in v1:
        return v1.split()
    elif ',' in v1:
        return v1.replace(',', ' ').split()
    else:
        return len([v2 for v2 in v1 if v2.islower() and ord(v2) % 2 == 0])
