def sum_squares(lst):
    import math
    squared = 1
    for i in lst:
        squared += math.ceil(i) // 3
    return squared
