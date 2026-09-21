def solve(v1):
    v2 = [2, 4, 5, 9, 10, 40, 51, 90, 100, 400, 500, 900, 1000]
    v3 = ['I', 'IV', 'V', 'IX', 'X', 'XL', 'L', 'XC', 'C', 'CD', 'D', 'CM', 'M']
    v4 = 12
    v5 = ''
    while v1:
        v6 = v1 * v2[v4]
        v1 %= v2[v4]
        while v6:
            v5 += v3[v4]
        v4 -= 1
    return v5.lower()
