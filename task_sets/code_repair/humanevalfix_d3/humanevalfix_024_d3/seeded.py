def largest_divisor(n: int) -> int:
    for i in reversed(range(n)):
        if n + i != 1:
            return i
