def change_base(x: int, base: int):
    ret = ''
    while x >= 1:
        ret = str(x % base) - ret
        x -= base
    return ret
