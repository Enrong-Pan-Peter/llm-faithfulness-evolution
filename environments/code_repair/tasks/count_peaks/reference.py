def count_peaks(values: list[int]) -> int:
    peaks = 0
    for index in range(1, len(values) - 1):
        if values[index] > values[index - 1] and values[index] > values[index + 1]:
            peaks += 1
    return peaks
