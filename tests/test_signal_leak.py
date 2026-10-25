"""Regression tests for Signal subscription memory leaks (issue #6744).

A Signal must not keep a removed DOM node (and by extension its subtree)
alive through its subscription bookkeeping: the WeakKeyDictionary entry
must be the only strong-reference path, so once the node is garbage
collected the subscription disappears too.
"""

from __future__ import annotations

import gc
import weakref

import pytest

from textual.app import App, ComposeResult
from textual.widgets import Input, TextArea


class SubscriptionLeakApp(App[None]):
    """Mounts one text box, lets the test remove it, then exposes it."""

    def compose(self) -> ComposeResult:
        yield TextArea()

    def on_mount(self) -> None:
        self.box_ref: weakref.ref[TextArea] | None = None

    def remove_box(self) -> None:
        box = self.query_one(TextArea)
        self.box_ref = weakref.ref(box)
        box.remove()


async def test_removed_text_area_is_not_pinned_by_signal_subscription():
    """A removed TextArea must be collectable despite its signal subscription."""
    app = SubscriptionLeakApp()
    async with app.run_test() as pilot:
        box = app.query_one(TextArea)
        # The subscription exists while mounted.
        signal = app.screen.text_selection_started_signal
        assert box in signal._subscriptions

        app.remove_box()
        await pilot.pause()
        # Removed from the DOM.
        assert not app.query(TextArea)

    # The app is stopped; drop our own reference and force a collection.
    del box
    gc.collect()
    assert app.box_ref is not None
    assert app.box_ref() is None, (
        "TextArea was garbage collected but the Signal subscription still "
        "pins it (issue #6744)"
    )


class InputLeakApp(App[None]):
    def compose(self) -> ComposeResult:
        yield Input()

    def on_mount(self) -> None:
        self.input_ref: weakref.ref[Input] | None = None

    def remove_input(self) -> None:
        field = self.query_one(Input)
        self.input_ref = weakref.ref(field)
        field.remove()


async def test_removed_input_is_not_pinned_by_signal_subscription():
    """A removed Input must be collectable despite its signal subscription."""
    app = InputLeakApp()
    async with app.run_test() as pilot:
        field = app.query_one(Input)
        signal = app.screen.text_selection_started_signal
        assert field in signal._subscriptions

        app.remove_input()
        await pilot.pause()
        assert not app.query(Input)

    del field
    gc.collect()
    assert app.input_ref is not None
    assert app.input_ref() is None, (
        "Input was garbage collected but the Signal subscription still "
        "pins it (issue #6744)"
    )


async def test_subscription_bookkeeping_survives_node_removal_while_app_runs():
    """While the app runs, removing the widget drops it from the subscriptions."""
    app = SubscriptionLeakApp()
    async with app.run_test() as pilot:
        box = app.query_one(TextArea)
        signal = app.screen.text_selection_started_signal
        assert box in signal._subscriptions

        app.remove_box()
        await pilot.pause()

        # Still referenced by the local `box` here, so the weak entry exists,
        # but publishing must not invoke anything for the removed node and
        # must not raise.
        signal.publish(None)
        await pilot.pause()
