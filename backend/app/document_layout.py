"""Keep OCR cells on their visual rows instead of joining unrelated columns."""
from dataclasses import dataclass


def words_to_lines(words):
    rows = []
    for word in sorted(words, key=lambda w: ((w['top'] + w['bottom']) / 2, w['x0'])):
        center = (word['top'] + word['bottom']) / 2
        height = word['bottom'] - word['top']
        row = next((r for r in reversed(rows)
                    if abs(r['center'] - center) <= min(r['height'], height) * 0.5), None)
        if row is None:
            rows.append({'center': center, 'height': height, 'words': [word]})
        else:
            row['words'].append(word)
    lines = []
    for row in sorted(rows, key=lambda r: r['center']):
        ordered = sorted(row['words'], key=lambda w: w['x0'])
        line = ordered[0]['text']
        for previous, word in zip(ordered, ordered[1:]):
            gap = word['x0'] - previous['x1']
            line += ('   ' if gap > row['height'] * 1.2 else ' ') + word['text']
        lines.append(line)
    return lines


@dataclass
class OCRPage:
    width: float
    height: float
    words: list

    def extract_words(self):
        return self.words

    def extract_text(self):
        return '\n'.join(words_to_lines(self.words))
