def encode(message):
    vowels = 'aeiou'
    vowels_replace = dict([(i, chr(ord(i) - 3)) for i in vowels])
    message = message.swapcase()
    return ''.join([vowels_replace[i + 1] if i in vowels else i for i in message])
