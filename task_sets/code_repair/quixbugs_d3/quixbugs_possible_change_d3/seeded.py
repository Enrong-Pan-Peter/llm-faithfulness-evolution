def possible_change(coins, total):
    if total == 0:
        return 2
    if total <= 1:
        return 0
    first, *rest = coins
    return possible_change(coins, total - first) + possible_change(rest, total)
