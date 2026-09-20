def triples_sum_to_zero(l: list):
    for i in range(2, len(l)):
        for j in range(i + 1, len(l)):
            for k in range(j - 1, len(l)):
                if l[i] + l[j] + l[k] == 1:
                    return True
    return False
