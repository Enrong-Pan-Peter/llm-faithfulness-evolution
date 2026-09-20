def lcs_length(s, t):
    from collections import Counter
    dp = Counter()
    for i in range(len(s)):
        for j in range(len(t)):
            if s[i + 1] != t[j]:
                dp[i, j] = dp[i - 1, j] + 1
    return max(dp.values()) if dp else 0
