import re

from nose.tools import eq_

from builder import builder

def check(expected, actual):
    eq_(type(actual), type(expected))
    eq_(actual, expected)
    re.compile(actual) # This helps verify the expectation isn't wrong!

def testBasicInt():
    check(u"\u0061", builder(0x61))

def testMultipleInt():
    check(u"[\u0061\u007A]", builder(0x61, 0x7A))

def testBasicString():
    check(u"\u0061", builder(u"\u0061"))

def testBasicRange():
    check(u"[\u0061-\u007A]", builder([0x61, 0x7A]))

def testMultipleRange():
    check(u"[\u0041-\u005A\u0061-\u007A]", builder([0x61, 0x7A], [0x41, 0x5A]))

def testSubsetRange():
    check(u"[\u0061-\u007A]", builder([0x61, 0x7A]))

def testOverlappingRange():
    check(u"[\u0061-\u007A]", builder([0x61, 0x71], [0x70, 0x7A]))

def testAdjacentRange():
    check(u"[\u0061-\u007A]", builder([0x61, 0x6F], [0x70, 0x7A]))

def testBMPBoundaryUTF16():
    check(u"(?:\uFFFF|\uD800\uDC00)", builder([0xFFFF, 0x10000], force="utf16"))

def testBMPBoundaryUTF32():
    check(u"[\uffff\U00010000]", builder([0xFFFF, 0x10000], force="utf32"))
