from __future__ import annotations

import pytest

from textual.app import App, ComposeResult
from textual.widgets import Tree
from textual.widgets.tree import RemoveRootError, UnknownNodeID


class VerseBody:
    pass


class VerseStar(VerseBody):
    pass


class VersePlanet(VerseBody):
    pass


class VerseMoon(VerseBody):
    pass


class VerseTree(Tree[VerseBody]):
    pass


class TreeClearApp(App[None]):
    """Tree clearing test app."""

    def compose(self) -> ComposeResult:
        yield VerseTree("White Sun", data=VerseStar())

    def on_mount(self) -> None:
        tree = self.query_one(VerseTree)
        node = tree.root.add("Londinium", VersePlanet())
        node.add_leaf("Balkerne", VerseMoon())
        node.add_leaf("Colchester", VerseMoon())
        node = tree.root.add("Sihnon", VersePlanet())
        node.add_leaf("Airen", VerseMoon())
        node.add_leaf("Xiaojie", VerseMoon())


async def test_tree_simple_clear() -> None:
    """Clearing a tree should keep the old root label and data."""
    async with TreeClearApp().run_test() as pilot:
        tree = pilot.app.query_one(VerseTree)
        assert len(tree.root.children) > 1
        pilot.app.query_one(VerseTree).clear()
        assert len(tree.root.children) == 0
        assert str(tree.root.label) == "White Sun"
        assert isinstance(tree.root.data, VerseStar)


async def test_tree_reset_with_label() -> None:
    """Resetting a tree with a new label should use the new label and set the data to None."""
    async with TreeClearApp().run_test() as pilot:
        tree = pilot.app.query_one(VerseTree)
        assert len(tree.root.children) > 1
        pilot.app.query_one(VerseTree).reset(label="Jiangyin")
        assert len(tree.root.children) == 0
        assert str(tree.root.label) == "Jiangyin"
        assert tree.root.data is None


async def test_tree_reset_with_label_and_data() -> None:
    """Resetting a tree with a label and data have that label and data used."""
    async with TreeClearApp().run_test() as pilot:
        tree = pilot.app.query_one(VerseTree)
        assert len(tree.root.children) > 1
        pilot.app.query_one(VerseTree).reset(label="Jiangyin", data=VersePlanet())
        assert len(tree.root.children) == 0
        assert str(tree.root.label) == "Jiangyin"
        assert isinstance(tree.root.data, VersePlanet)


async def test_remove_node():
    async with TreeClearApp().run_test() as pilot:
        tree = pilot.app.query_one(VerseTree)
        assert len(tree.root.children) == 2
        tree.root.children[0].remove()
        assert len(tree.root.children) == 1


async def test_remove_node_children():
    async with TreeClearApp().run_test() as pilot:
        tree = pilot.app.query_one(VerseTree)
        assert len(tree.root.children) == 2
        assert len(tree.root.children[0].children) == 2
        tree.root.children[0].remove_children()
        assert len(tree.root.children) == 2
        assert len(tree.root.children[0].children) == 0


async def test_tree_remove_children_of_root():
    """Test removing the children of the root."""
    async with TreeClearApp().run_test() as pilot:
        tree = pilot.app.query_one(VerseTree)
        assert len(tree.root.children) > 1
        tree.root.remove_children()
        assert len(tree.root.children) == 0


async def test_attempt_to_remove_root():
    """Attempting to remove the root should be an error."""
    async with TreeClearApp().run_test() as pilot:
        with pytest.raises(RemoveRootError):
            pilot.app.query_one(VerseTree).root.remove()


async def test_clear_resets_node_index() -> None:
    """Clearing a tree should drop discarded nodes from the node index and
    register the new root, so get_node_by_id can't return stale nodes
    (https://github.com/Textualize/textual/issues/6712)."""
    async with TreeClearApp().run_test() as pilot:
        tree = pilot.app.query_one(VerseTree)
        old_child_id = tree.root.children[0].id
        old_child = tree.get_node_by_id(old_child_id)

        tree.clear()

        # The new root is indexed, and its ID (reused from the old root) now
        # maps to it rather than to the discarded root.
        assert tree._tree_nodes[tree.root.id] is tree.root
        assert tree.get_node_by_id(tree.root.id) is tree.root
        # Pre-clear nodes are gone from the index.
        assert old_child_id not in tree._tree_nodes
        assert old_child_id != tree.root.id or old_child is not tree.root
        with pytest.raises(UnknownNodeID):
            tree.get_node_by_id(old_child_id)
        # Only the fresh root remains indexed.
        assert len(tree._tree_nodes) == 1


async def test_reset_resets_node_index() -> None:
    """reset() goes through clear(), so it must rebuild the node index too."""
    async with TreeClearApp().run_test() as pilot:
        tree = pilot.app.query_one(VerseTree)
        old_child_id = tree.root.children[0].id

        tree.reset(label="Jiangyin")

        assert tree.get_node_by_id(tree.root.id) is tree.root
        with pytest.raises(UnknownNodeID):
            tree.get_node_by_id(old_child_id)
        assert len(tree._tree_nodes) == 1
