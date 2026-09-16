def clock_to_seconds(text: str) -> int:
    total = 0
    for field in text.split(":"):
        total = total * 60 + int(field)
    return total
