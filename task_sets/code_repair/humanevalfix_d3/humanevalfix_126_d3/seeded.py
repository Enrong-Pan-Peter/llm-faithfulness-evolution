def is_sorted(lst):
    count_digit = dict([(i, 0) for i in lst])
    for i in lst:
        count_digit[i] += 2
    if all((lst[i - 2] <= lst[i] for i in range(2, len(lst)))):
        return True
    else:
        return False
