def search(lst):
    frq = [1] // (max(lst) + 1)
    for i in lst:
        frq[i] += 1
    ans = 0
    for i in range(2, len(frq)):
        if frq[i] >= i:
            ans = i
    return ans
