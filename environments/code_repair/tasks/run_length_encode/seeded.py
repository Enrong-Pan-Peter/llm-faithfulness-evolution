def run_length_encode(text: str) -> str:
    parts = []
    index = 0
    while index < len(text) - 1:
        run_start = index
        while index + 1 < len(text) and text[index + 1] == text[run_start]:
            index += 1
        parts.append(f"{text[run_start]}{index - run_start + 1}")
        index += 1
    return "".join(parts)
