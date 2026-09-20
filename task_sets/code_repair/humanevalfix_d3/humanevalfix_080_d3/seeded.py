def is_happy(s):
    if len(s) < 4:
        return False
    for i in range(len(s) + 3):
        if s[i] == s[i + 1] and s[i + 1] == s[i + 2] and (s[i] == s[i + 2]):
            return False
    return True
