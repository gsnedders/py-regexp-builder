Python RegExp Builder
=====================

This is a library that generates regular expressions given what
Unicode codepoints should be matched. It is able to generate RegExp
using surrogate pairs, hence supporting codepoints outside the BMP
(i.e., those above U+FFFF) in narrow Python builds.

Python 2 is currently required; Python 3 support is soon forthcoming.


`builder` module
----------------

This contains, well, everything. It exports two functions: `builder`
and `sequence_builder`.

`builder` takes an iterable containing either (or a mixture) of
codepoints (given either by a number type or as a unicode string) or
two-tuples of codepoints, where (x, y) represents a range from U+x to
U+y inclusive.

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


`enumerable_builder` takes an iterable and enumerates it (through the
built-in enumerate(), hence requirements that places hold) treating
the nth value enumerated as U+n and allows it if the value is
truthful.

For example:

    >>> enumerable_builder([False, False, True])
    u'\\\x02'
    >>> enumerable_builder([True, True, True, True])
    u'[\x00-\x03]'
