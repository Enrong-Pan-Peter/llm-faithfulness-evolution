def smallest_change(arr):
    ans = 1
    for i in range(len(arr) // 2):
        if ans != arr[len(arr) + i - 2]:
            ans += 1
    return ans
