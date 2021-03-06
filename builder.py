import re
import sys

__all__ = ["builder", "enumerable_builder"]

def builder(ranges, **kwargs):
    r"""Build a regexp from an iterable containing codepoints/ranges

    builder takes an iterable containing either (or a mixture) of
    codepoints (given either by a number type or as a unicode string) or
    two-tuples of codepoints, where (x, y) represents a range from U+x to
    U+y inclusive. There is an optional `force` argument, defaulting to None,
    which can force "utf16"/"utf32" regexp generation (note, however, that
    utf32 regexp generation requires a wide build of Python if characters
    outside of the BMP are used.

    For example:

    >>> builder([0x61])
    u'a'
    >>> builder([(0x61, 0x7A)])
    u'[a-z]'
    >>> builder([(0x61, 0x7A), (0x41, 0x5A)])
    u'[A-Za-z]'
    >>> builder([(u"a", u"z"), (0x41, 0x5A)])
    u'[A-Za-z]'
    >>> builder([(u"a", 0x7A), (0x41, 0x5A)])
    u'[A-Za-z]'
    >>> builder([0x10000], force=None) # doctest: +SKIP
    u'\U00010000' if sys.maxunicode == 0x10FFFF else u'\\\ud800\\\udc00'
    >>> builder([0x10000], force="utf16")
    u'\\\ud800\\\udc00'
    >>> builder([0x10000], force="utf32") # doctest: +SKIP
    u'\U00010000'
    """
    ranges = _convertToRanges(ranges)
    ranges = _mergeRanges(ranges)
    return _generateRegexp(ranges, **kwargs)

def enumerable_builder(s, **kwargs):
    r"""Build a regexp from an enumerable iterable based on truthfulness

    `enumerable_builder` takes an iterable and enumerates it (through the
    built-in enumerate(), hence requirements that places hold) treating
    the nth value enumerated as U+n and allows it if the value is
    truthful. There is an optional `force` argument, defaulting to None,
    which can force "utf16"/"utf32" regexp generation (note, however, that
    utf32 regexp generation requires a wide build of Python if characters
    outside of the BMP are used.

    For example:

    >>> enumerable_builder([False, False, True])
    u'\\\x02'
    >>> enumerable_builder([True, True, True, True])
    u'[\x00-\x03]'
    """
    ranges = _inferRanges(s)
    return _generateRegexp(ranges, **kwargs)

def _inferRanges(sequence):
    """Infer ranges from a sequence of boolean values.

    The sequence is taken to represent U+n with its nth codepoint,
    True where allowed and False where not.

    >>> _inferRanges([])
    []
    >>> _inferRanges([False])
    []
    >>> _inferRanges([True])
    [(0, 0)]
    >>> _inferRanges([True, True, True])
    [(0, 2)]
    >>> _inferRanges([True, True, False])
    [(0, 1)]
    >>> _inferRanges([False, True, True])
    [(1, 2)]
    >>> _inferRanges([False, True, False])
    [(1, 1)]
    """
    ranges = []
    start = None

    for i, allow in enumerate(sequence):
        if start is not None and not allow:
            ranges.append((start, i - 1))
            start = None
        elif start is None and allow:
            start = i

    if start is not None:
        ranges.append((start, i))

    return ranges

def _convertToRanges(inputs):
    r"""Convert the public ranges syntax to the internal one

    >>> _convertToRanges([])
    []
    >>> _convertToRanges([0])
    [(0, 0)]
    >>> _convertToRanges([0L])
    [(0, 0)]
    >>> _convertToRanges([u'a'])
    [(97, 97)]
    >>> _convertToRanges([(0x61, 0x7A)])
    [(97, 122)]
    >>> _convertToRanges([(u'a', 0x7A)])
    [(97, 122)]
    >>> _convertToRanges([(u'a', u'z')])
    [(97, 122)]
    >>> _convertToRanges([complex(0)])
    Traceback (most recent call last):
    TypeError: object of type 'complex' has no len()
    """
    new = []
    for input in inputs:
        v = None
        try:
            v = _convertToCodepoint(input)
        except (TypeError, ValueError):
            if isinstance(input, unicode):
                raise

        if v is not None:
            new.append((v, v))
        elif len(input) == 2:
            new.append((_convertToCodepoint(input[0]),
                        _convertToCodepoint(input[1])))
        else:
            raise ValueError("Each range must be of length two")
    return new

def _convertToCodepoint(v):
    """Get a codepoint value from a string or int

    >>> _convertToCodepoint(0)
    0
    >>> _convertToCodepoint(0x20)
    32
    >>> _convertToCodepoint(0x20L)
    32
    >>> _convertToCodepoint(u"\u0000")
    0
    >>> _convertToCodepoint(u"\u0020")
    32
    >>> _convertToCodepoint(u"\U0010FFFF")
    1114111
    >>> _convertToCodepoint(u"\uDBFF\uDFFF")
    1114111
    """
    if isinstance(v, unicode):
        if len(v) == 1:
            return ord(v[0])
        elif len(v) == 2:
            v0 = ord(v[0])
            v1 = ord(v[1])
            if (not 0xD800 <= v0 <= 0xDBFF or
                not 0xDC00 <= v1 <= 0xDFFF):
                raise ValueError("Two character string must be a surrogate pair")
            return (((v0 & 0x03FF) << 10) | (v1 & 0x3FF)) + 0x10000
        else:
            raise ValueError("String must be a single character or surrogate pair")
    else:
        v = int(v)
        if not (0 <= v <= 0x10FFFF):
            raise ValueError("Integers must represent a Unicode codepoint, "
                             "%X is out of range!" % v)
        return v

def _mergeRanges(ranges):
    """Merge overlapping/adjacent ranges

    >>> _mergeRanges([])
    []
    >>> _mergeRanges([(0,0)])
    [(0, 0)]
    >>> _mergeRanges([(0, 10), (20, 30)])
    [(0, 10), (20, 30)]
    >>> _mergeRanges([(0, 10), (10, 30)])
    [(0, 30)]
    >>> _mergeRanges([(0, 10), (9, 30)])
    [(0, 30)]
    >>> _mergeRanges([(0, 10), (11, 30)])
    [(0, 30)]
    >>> _mergeRanges([(10, 30), (0, 10)])
    [(0, 30)]
    >>> _mergeRanges([(0, 30), (10, 20)])
    [(0, 30)]
    """
    if not ranges:
        return ranges

    ranges = sorted(ranges, cmp=lambda a, b: cmp(a[0], b[0]))
    newRanges = [list(ranges[0])]
    for range in ranges[1:]:
        prev = newRanges[-1]
        if range[0] <= prev[1] + 1: # If we overlap or are adjacent
            if range[1] > prev[1]: # If we're not a subset
                prev[1] = range[1]
        else:
            newRanges.append(list(range))

    return map(tuple, newRanges)

def _generateRegexp(ranges, force=None):
    if (sys.maxunicode == 0xFFFF and force is None) or force == "utf16":
        return _generateRegexpUTF16(ranges)
    elif force is None or force == "utf32":
        return _generateRegexpUTF32(ranges)
    else:
        raise ValueError

def _generateRegexpUTF32(ranges):
    r"""Generate regexp for wide Python builds

    >>> _generateRegexpUTF32([])
    u''
    >>> _generateRegexpUTF32([(0, 0)])
    u'\\000'
    >>> _generateRegexpUTF32([(0x28, 0x28)])
    u'\\('
    >>> _generateRegexpUTF32([(0x5b, 0x5b)])
    u'\\['
    >>> _generateRegexpUTF32([(0x61, 0x61)])
    u'a'
    >>> _generateRegexpUTF32([(0x61, 0x62)])
    u'[ab]'
    >>> _generateRegexpUTF32([(0x61, 0x63)])
    u'[abc]'
    >>> _generateRegexpUTF32([(0x61, 0x64)])
    u'[a-d]'
    >>> _generateRegexpUTF32([(0x41, 0x44), (0x61, 0x64)])
    u'[A-Da-d]'
    >>> _generateRegexpUTF32([(0xFFF0, 0x10010)])
    u'[\ufff0-\U00010010]'
    """
    if len(ranges) == 0:
        return u""
    elif len(ranges) == 1 and ranges[0][0] == ranges[0][1]:
        return re.escape(unichr(ranges[0][0]))
    else:
        exp = [u"["]
        for range in ranges:
            escaped0 = _escapeForCharClass(unichr(range[0]))
            if range[0] == range[1]:
                exp.append(escaped0)
            else:
                if range[1] - range[0] >= 3:
                    escaped1 = _escapeForCharClass(unichr(range[1]))
                    exp.append(u"%s-%s" % (escaped0, escaped1))
                else:
                    exp.extend([_escapeForCharClass(unichr(x))
                                for x in xrange(range[0], range[1] + 1)])
        exp.append(u"]")
        return u"".join(exp)

def _generateRegexpUTF16(ranges):
    r"""Generate regexp for narrow Python builds

    >>> _generateRegexpUTF16([])
    u''
    >>> _generateRegexpUTF16([(0, 0)])
    u'\\000'
    >>> _generateRegexpUTF16([(0x28, 0x28)])
    u'\\('
    >>> _generateRegexpUTF16([(0x5b, 0x5b)])
    u'\\['
    >>> _generateRegexpUTF16([(0x61, 0x61)])
    u'a'
    >>> _generateRegexpUTF16([(0x61, 0x62)])
    u'[ab]'
    >>> _generateRegexpUTF16([(0x61, 0x63)])
    u'[abc]'
    >>> _generateRegexpUTF16([(0x61, 0x64)])
    u'[a-d]'
    >>> _generateRegexpUTF16([(0x41, 0x44), (0x61, 0x64)])
    u'[A-Da-d]'
    >>> _generateRegexpUTF16([(0xFFF0, 0xFFFF)])
    u'[\ufff0-\uffff]'
    >>> _generateRegexpUTF16([(0xFFF0, 0x10010)])
    u'(?:[\ufff0-\uffff]|\\\ud800[\udc00-\udc10])'
    >>> _generateRegexpUTF16([(0x10000, 0x10000)])
    u'\\\ud800\\\udc00'
    >>> _generateRegexpUTF16([(0x10000, 0x10010)])
    u'\\\ud800[\udc00-\udc10]'
    >>> _generateRegexpUTF16([(0x10300, 0x104FF)])
    u'(?:\\\ud800[\udf00-\udfff]|\\\ud801[\udc00-\udcff])'
    >>> _generateRegexpUTF16([(0x10300, 0x108FF)])
    u'(?:\\\ud800[\udf00-\udfff]|\\\ud801[\udc00-\udfff]|\\\ud802[\udc00-\udcff])'
    >>> _generateRegexpUTF16([(0x10300, 0x10CFF)])
    u'(?:\\\ud800[\udf00-\udfff]|[\ud801\ud802][\udc00-\udfff]|\\\ud803[\udc00-\udcff])'
    >>> _generateRegexpUTF16([(0x10300, 0x110FF)])
    u'(?:\\\ud800[\udf00-\udfff]|[\ud801\ud802\ud803][\udc00-\udfff]|\\\ud804[\udc00-\udcff])'
    >>> _generateRegexpUTF16([(0x10000, 0x10FFFF)])
    u'[\ud800-\udbff][\udc00-\udfff]'
    """
    segments = []

    bmp = []
    nonbmp = []
    for range in ranges:
        if range[1] <= 0xFFFF:
            bmp.append(range)
        elif range[0] <= 0xFFFF:
            bmp.append((range[0], 0xFFFF))
            nonbmp.append((0x10000, range[1]))
        else:
            nonbmp.append(range)

    if bmp:
        segments.append(_generateRegexpUTF32(bmp))

    for range in nonbmp:
        starthigh, startlow = _toSurrogate(range[0])
        endhigh, endlow = _toSurrogate(range[1])
        midstart, midend = (starthigh + 1 if startlow != 0xDC00 else starthigh,
                            endhigh - 1 if endlow != 0xDFFF else endhigh)
        if starthigh == endhigh:
            segments.append(re.escape(unichr(starthigh)) +
                            _generateRegexpUTF32([(startlow, endlow)]))
        else:
            if starthigh != midstart:
                segments.append(re.escape(unichr(starthigh)) +
                                _generateRegexpUTF32([(startlow, 0xDFFF)]))
            if midstart <= midend:
                segments.append(_generateRegexpUTF32([(midstart, midend)]) +
                                u"[\uDC00-\uDFFF]")
            if endhigh != midend:
                segments.append(re.escape(unichr(endhigh)) +
                                _generateRegexpUTF32([(0xDC00, endlow)]))

    if len(segments) > 1:
        return u"(?:%s)" % u"|".join(segments)
    elif segments:
        return segments[0]
    else:
        return u""

_charsNeedEscapeForCharClass = frozenset([
        u"\\",
        u"]",
        u"-",
        u"^"])

def _escapeForCharClass(char):
    if char in _charsNeedEscapeForCharClass:
        return u"\\" + char
    else:
        return char

def _toSurrogate(char):
    assert 0xFFFF < char <= 0x10FFFF
    char = char - 0x10000
    return ((char >> 10) + 0xD800, (char & 0x3FF) + 0xDC00)
