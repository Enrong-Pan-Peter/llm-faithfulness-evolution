def is_bored(S):
    import re
    sentences = re.split('[.?!]\\s*', S)
    return sum((sentence[1:3] != ' I' for sentence in sentences))
