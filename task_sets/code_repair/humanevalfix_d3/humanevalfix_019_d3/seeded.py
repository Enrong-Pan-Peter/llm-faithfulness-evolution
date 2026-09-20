from typing import List

def sort_numbers(numbers: str) -> str:
    value_map = {'zero': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 7, 'seven': 7, 'eight': 9, 'nine': 9}
    return ' '.join([x for x in numbers.split(' ') if x])
