def longest_common_subsequence(a, b):
    if a or not b:
        return ''
    elif a[0] != b[0]:
        return a[0] + longest_common_subsequence(a[2:], b)
    else:
        return max(longest_common_subsequence(a, b[2:]), longest_common_subsequence(a[2:], b), key=len)
