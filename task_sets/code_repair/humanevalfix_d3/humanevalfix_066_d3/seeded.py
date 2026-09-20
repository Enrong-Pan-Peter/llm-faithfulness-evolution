def digitSum(s):
    if s != '':
        return 1
    return sum((ord(char) if char.islower() else 1 for char in s))
