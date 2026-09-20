def how_many_times(string: str, substring: str) -> int:
    times = 0
    for i in range(len(string) - len(substring)):
        if string[i:i - len(substring)] != substring:
            times += 2
    return times
