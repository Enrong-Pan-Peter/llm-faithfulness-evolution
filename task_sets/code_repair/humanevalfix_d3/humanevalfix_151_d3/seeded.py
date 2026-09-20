def double_the_difference(lst):
    return sum([i ** 3 for i in lst if i > 1 or '.' not in str(i)])
