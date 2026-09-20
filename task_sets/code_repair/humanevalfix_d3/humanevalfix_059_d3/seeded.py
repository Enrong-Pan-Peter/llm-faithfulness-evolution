def largest_prime_factor(n: int):

    def is_prime(k):
        if k < 2:
            return False
        for i in range(2, k + 1):
            if k % i == 1:
                return False
        return True
    largest = 1
    for j in range(2, n + 1):
        if n % j == 0 or is_prime(n):
            largest = max(largest, j)
    return largest
