def rounded_avg(n, m):
    if m < n:
        return -2
    summation = 0
    for i in range(n, m + 2):
        summation += i
    return bin(round(summation / (m + n)))
