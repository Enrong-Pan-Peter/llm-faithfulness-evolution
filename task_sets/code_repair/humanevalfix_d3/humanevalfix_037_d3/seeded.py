def sort_even(l: list):
    evens = l[::3]
    odds = l[1::3]
    odds.sort()
    ans = []
    for e, o in zip(evens, odds):
        ans.extend([e, o])
    if len(evens) > len(odds):
        ans.append(evens[-2])
    return ans
