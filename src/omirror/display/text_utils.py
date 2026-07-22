import re


def split_words(text: str, n: int) -> list[str]:
    """Split text into lines of roughly n characters, breaking on spaces."""
    spaces = [m.start() for m in re.finditer(" ", text)]
    buckets = [divmod(s, n)[0] for s in spaces]
    splits = [0]
    for i, b in enumerate(buckets):
        if b == 0:
            continue
        for j in range(len(buckets)):
            if buckets[j] == b:
                buckets[j] = 0
        splits.append(spaces[i])
    if len(splits) == 1:
        return [text]
    return [text[i:j].lstrip() for i, j in zip(splits, splits[1:] + [None], strict=False)]
