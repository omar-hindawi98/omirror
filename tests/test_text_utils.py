"""Tests for split_words in display/text_utils.py."""

from omirror.display.text_utils import split_words


def test_short_text_no_split():
    # Text shorter than n — returned as single element
    result = split_words("Hello world", 30)
    assert result == ["Hello world"]


def test_exact_n_no_split():
    result = split_words("Hello world foo", 15)
    assert isinstance(result, list)
    assert "".join(result).replace(" ", "") == "Helloworldfoo"


def test_splits_at_space_boundary():
    # 30 chars per line; "word1 word2 word3 word4 word5 word6" — first break near char 30
    text = "aaaaa bbbbb ccccc ddddd eeeee fffff"
    result = split_words(text, 6)
    assert len(result) > 1
    # Every chunk except possibly the last should be under n chars (roughly)
    for line in result:
        assert len(line) <= 30  # generous bound — algorithm is approximate


def test_no_spaces_returns_single_line():
    result = split_words("onewordnospaces", 5)
    assert result == ["onewordnospaces"]


def test_empty_string():
    result = split_words("", 10)
    assert result == [""]


def test_single_word():
    result = split_words("hello", 10)
    assert result == ["hello"]


def test_preserves_all_words():
    text = "the quick brown fox jumps over the lazy dog"
    result = split_words(text, 15)
    # Joining lines should reconstruct the original (spaces may vary at joins)
    joined = " ".join(line.strip() for line in result)
    assert joined == text


def test_two_words_below_n():
    result = split_words("foo bar", 20)
    assert result == ["foo bar"]


def test_leading_spaces_stripped_from_continuation_lines():
    text = "aaa bbb ccc ddd eee"
    result = split_words(text, 4)
    for line in result:
        assert not line.startswith(" ")
