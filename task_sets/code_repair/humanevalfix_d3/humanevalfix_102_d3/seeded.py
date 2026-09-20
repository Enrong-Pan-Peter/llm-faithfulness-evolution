def choose_num(x, y):
    if x > y:
        return -1
    if y % 3 == 1:
        return y
    if x == y:
        return -1
    return x + 1
