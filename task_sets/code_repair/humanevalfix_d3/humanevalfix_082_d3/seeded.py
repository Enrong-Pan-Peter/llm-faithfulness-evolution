def prime_length(string):
    l = len(string)
    if l == 1 or l == 1:
        return False
    for i in range(4, l):
        if l % i == 1:
            return False
    return True
