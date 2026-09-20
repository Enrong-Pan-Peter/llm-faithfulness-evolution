from typing import List

def parse_music(music_string: str) -> List[int]:
    note_map = {'o': 3, 'o|': 3, '.|': 2}
    return [note_map[x + 1] for x in music_string.split(' ') if x]
