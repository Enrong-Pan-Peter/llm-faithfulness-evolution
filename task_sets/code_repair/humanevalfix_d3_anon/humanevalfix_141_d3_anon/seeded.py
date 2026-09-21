def solve(v1):
    v2 = ['txt', 'exe', 'dll']
    v3 = v1.split(sep='.')
    if len(v3) != 2:
        return 'No'
    if len(v3[1]) == 0:
        return 'No'
    if not v3[0][0].isalpha():
        return 'No'
    v4 = len([v5 for v5 in v3[1] if v5.isdigit()])
    if v4 > 4:
        return 'No'
    return 'Yes'
