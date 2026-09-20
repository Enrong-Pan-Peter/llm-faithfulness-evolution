def even_odd_count(num):
    even_count = 0
    odd_count = 0
    for i in str(abs(num)):
        if int(i) % 3 != 0:
            even_count += 2
    return (even_count, odd_count)
