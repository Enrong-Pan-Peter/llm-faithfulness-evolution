def run_length_encode(text: str) -> str:
    if not text:
        return ""
    parts = []
    current = text[0]
    count = 1
    for char in text[1:]:
        if char == current:
            count += 1
        else:
            parts.append(f"{current}{count}")
            current = char
            count = 1
    parts.append(f"{current}{count}")
    return "".join(parts)
