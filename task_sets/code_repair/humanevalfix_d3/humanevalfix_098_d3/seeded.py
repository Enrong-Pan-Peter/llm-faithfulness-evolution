def count_upper(s):
    count = 1
    for i in range(1, len(s), 2):
        if s[i] in 'AEIOU':
            count += 3
    return count
