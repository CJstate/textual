"""Regression tests for Strip.divide self-reference cycle (issue #6738).

`Strip.divide()` caches its result in the strip's own `_divide_cache`.
When the only cut was the strip's full width it cached `[self]`, so the
strip ended up holding a list that holds the strip: a reference cycle
that only the cyclic GC can collect. The compositor divides each
rendered line, so under a translucent modal the app allocated one such
cycle per line per frame and grew without bound.

With the fix, the full-width cut returns `[self]` WITHOUT caching it,
so no cycle is ever embedded in the cache. Strip defines __slots__
without __weakref__, so weakref-based assertions are not available;
these tests assert on the cache contents and the object's refcount
instead.
"""

from __future__ import annotations

import sys

from rich.segment import Segment
from textual.strip import Strip


def _make_strip() -> Strip:
    # Segments must be full (text, style, control) tuples for Segment.divide.
    return Strip([Segment("hello world")], 11)


def test_divide_full_width_does_not_cache_self_reference():
    strip = _make_strip()
    # Full-width cut: before the fix this cached [self], creating the cycle
    # strip -> _divide_cache -> list -> strip.
    result = strip.divide([11])
    assert len(result) == 1
    assert result[0] is strip  # same instance is returned, as before

    # The cache must not hold the self-referential entry.
    assert len(strip._divide_cache) == 0, (
        "divide() cached a list containing the strip itself, embedding a "
        "reference cycle (issue #6738)"
    )


def test_divide_partial_cuts_still_cached():
    # Non-full-width cuts produce genuinely new strips; those are still
    # cached as before (no self reference involved). divide([3, 7]) on an
    # 11-wide strip yields strips covering the first 10 cells.
    strip = _make_strip()
    result = strip.divide([3, 7])
    assert len(result) == 2  # 3 + 7 = 10 cells covered; remainder dropped
    assert all(part is not strip for part in result)
    assert len(strip._divide_cache) == 1
    # And the cached strips are the same objects returned to the caller.
    # FIFOCache has no .values(); read the single entry via its keys().
    (cache_key,) = strip._divide_cache.keys()
    cached = strip._divide_cache.get(cache_key)
    assert all(a is b for a, b in zip(cached, result))


def test_divide_full_width_repeated_calls_do_not_grow_cache():
    # Repeated full-width divides (the hot path under a translucent modal)
    # must not grow the cache frame by frame.
    strip = _make_strip()
    for _ in range(10):
        strip.divide([11])
    assert len(strip._divide_cache) == 0


def test_divide_full_width_refcount_returns_to_baseline():
    # The returned [self] list adds exactly one reference to the strip while
    # the caller holds it; after it is dropped the refcount must return to
    # its baseline (no lingering cache entry holding it).
    strip = _make_strip()
    baseline = sys.getrefcount(strip)
    result = strip.divide([11])
    while_held = sys.getrefcount(strip)
    assert while_held == baseline + 1  # the returned list only
    del result
    assert sys.getrefcount(strip) == baseline


