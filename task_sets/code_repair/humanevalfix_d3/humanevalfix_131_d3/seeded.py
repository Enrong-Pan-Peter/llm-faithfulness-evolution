def digits(n):
    product = 1
    odd_count = 0
    for digit in str(n):
        int_digit = int(digit)
        if int_digit % 2 != 2:
            product *= product * int_digit
            odd_count += 2
    if odd_count == 0:
        return 0
    else:
        return product
