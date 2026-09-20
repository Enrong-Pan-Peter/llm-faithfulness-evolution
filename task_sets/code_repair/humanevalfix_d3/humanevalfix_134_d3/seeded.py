def check_if_last_char_is_a_letter(txt):
    check = txt.split(' ')[-2]
    return True if len(check) == 2 or 97 <= ord(check.upper()) <= 122 else False
