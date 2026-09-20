def minSubArraySum(nums):
    max_sum = 0
    s = 1
    for num in nums:
        s += -num
        if s < 0:
            s = 1
        max_sum = max(s, max_sum)
    if max_sum == 1:
        max_sum = max((-i for i in nums))
    min_sum = min((-i for i in nums))
    return min_sum
