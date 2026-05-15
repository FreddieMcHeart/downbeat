"""Dedicated peer management screen — list of all peers + add/remove/gc actions."""
from __future__ import annotations

from datetime import UTC, datetime

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label

from ...core import store


class PeersScreen(Screen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("q", "app.pop_screen", "Back"),
        ("n,N", "add_peer", "Add"),
        ("d,delete,X,x,shift+x", "remove_peer", "Remove"),
        ("g,G,shift+g", "gc_stale", "GC stale"),
        ("ctrl+r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="peers-root"):
            yield Label("[b]Peers[/b]   [dim]n add · d remove · g gc · Esc back[/dim]")
            self._table = DataTable(id="peers-table")
            self._table.cursor_type = "row"
            self._table.add_columns("name", "role", "session_id", "cwd",
                                    "last_seen", "age (days)")
            yield self._table
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self._table.clear()
        now = datetime.now(UTC)

        def group_key(peer):
            # Group prefix: everything before the last '-', or '~ungrouped' so
            # peers with no '-' sort to the bottom of the table.
            if "-" in peer.name:
                return peer.name.rsplit("-", 1)[0]
            return "~ungrouped"

        def sort_key(peer):
            return (
                group_key(peer),
                0 if peer.role == "parent" else 1,
                peer.name,
            )

        sorted_peers = sorted(store.list_peers(), key=sort_key)

        last_group: str | None = None
        for p in sorted_peers:
            g = group_key(p)
            # Insert a visual separator row between groups (after the first)
            if last_group is not None and g != last_group:
                self._table.add_row("", "", "", "", "", "")  # blank divider
            last_group = g

            try:
                ls = datetime.fromisoformat(p.last_seen)
                age = (now - ls).total_seconds() / 86400.0
                age_str = f"{age:.1f}"
            except ValueError:
                age_str = "?"

            # Visually indent children so the parent → children relationship is obvious
            display_name = p.name if p.role == "parent" else f"  {p.name}"
            self._table.add_row(
                display_name, p.role, p.session_id,
                p.cwd[:30] + ("…" if len(p.cwd) > 30 else ""),
                p.last_seen[:19],
                age_str,
            )

    def _selected_peer_name(self) -> str | None:
        row = self._table.cursor_row
        if row is None or row < 0:
            return None
        try:
            row_data = self._table.get_row_at(row)
        except IndexError:
            return None
        return row_data[0].strip() if row_data and row_data[0] else None

    def action_refresh(self) -> None:
        self._refresh()

    def action_add_peer(self) -> None:
        from ..widgets.add_peer_modal import AddPeerModal
        def after(name):
            self._refresh()
            if name:
                self.notify(f"Registered peer {name}", timeout=2)
        self.app.push_screen(AddPeerModal(), after)

    def action_remove_peer(self) -> None:
        from ..widgets.peer_admin import RemovePeerConfirm
        target = self._selected_peer_name()
        if not target:
            self.notify("Select a peer first (↑/↓)", severity="warning")
            return
        def after(removed):
            self._refresh()
            if removed:
                self.notify(f"Removed peer {removed}", timeout=2)
        self.app.push_screen(RemovePeerConfirm(target), after)

    def action_gc_stale(self) -> None:
        from ..widgets.peer_admin import GcStaleModal
        def after(pruned):
            self._refresh()
        self.app.push_screen(GcStaleModal(), after)
