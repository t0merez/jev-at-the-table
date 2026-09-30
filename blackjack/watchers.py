"""Watchers: things the table reports to as the game runs, such as a log file or the terminal.

Only the table talks to a watcher. Players never see watchers, and watchers
only receive read-only data (frozen dataclasses, tuples and read-only
mappings), so a watcher can observe the game but can't change it or reach
any player.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from blackjack.api import Action, DecisionView, RoundResult
from blackjack.cards import Card
from blackjack.rules import TableRules


@dataclass(frozen=True)
class SeatInfo:
    """Who sits at the table, as a watcher sees it. No access to the player itself."""

    name: str
    player_type: str
    bankroll: int


class TableWatcher:
    """Base class. Override whichever events you care about."""

    def start(self, rules: TableRules, seats: tuple[SeatInfo, ...]) -> None:
        pass

    def decision(self, round_no: int, player_name: str, view: DecisionView, action: Action) -> None:
        pass

    def round_end(
        self, round_no: int, dealer_cards: tuple[Card, ...], dealer_total: int, results: Mapping[str, RoundResult]
    ) -> None:
        pass

    def round_cancelled(self, round_no: int) -> None:
        """The round was stopped part-way and undone; its bets were returned."""

    def end(self, final_bankrolls: Mapping[str, int], stop_reason: str | None = None) -> None:
        """stop_reason is None when the session ran to the end, otherwise why it stopped early."""


def _cards(cards) -> str:
    return " ".join(str(card) for card in cards)


class TerminalPrinter(TableWatcher):
    """Prints decisions and round results, and a summary at the end.

    hide_players: names whose decisions and results aren't printed, e.g. a
    human who already sees their own hand. show_dealer: whether to print the
    dealer's final hand.
    """

    def __init__(self, hide_players: tuple[str, ...] = (), show_dealer: bool = True):
        self._hide = set(hide_players)
        self._show_dealer = show_dealer
        self._start_bankrolls: dict[str, int] = {}
        self._printed_round = None  # the round whose header is already printed

    def start(self, rules: TableRules, seats: tuple[SeatInfo, ...]) -> None:
        self._start_bankrolls = {seat.name: seat.bankroll for seat in seats}
        limits = f"{rules.min_bet}-{rules.max_bet}" if rules.max_bet else f"min {rules.min_bet}"
        print(f"Table: {rules.num_decks} decks, bets {limits}. Players: {', '.join(self._start_bankrolls)}")

    def decision(self, round_no: int, player_name: str, view: DecisionView, action: Action) -> None:
        if player_name in self._hide:
            return
        if self._printed_round != round_no:
            print(f"\nRound {round_no}, dealer shows {view.dealer_upcard}")
            self._printed_round = round_no
        soft = "soft " if view.is_soft else ""
        print(f"  {player_name}: {_cards(view.my_cards)} ({soft}{view.my_total}) -> {action.value}")

    def round_end(
        self, round_no: int, dealer_cards: tuple[Card, ...], dealer_total: int, results: Mapping[str, RoundResult]
    ) -> None:
        shown = {name: result for name, result in results.items() if name not in self._hide}
        if not shown and not self._show_dealer:
            return
        if self._printed_round != round_no:  # no decisions printed this round (e.g. a blackjack)
            print(f"\nRound {round_no}")
            self._printed_round = round_no
        if self._show_dealer:
            print(f"  Dealer: {_cards(dealer_cards)} = {dealer_total}")
        for name, result in shown.items():
            for hand in result.hands:
                print(f"  {name}: {_cards(hand.cards)} -> {hand.outcome.value} ({hand.net:+}), bankroll {result.bankroll_after}")

    def round_cancelled(self, round_no: int) -> None:
        print(f"\nRound {round_no} cancelled; bets returned")

    def end(self, final_bankrolls: Mapping[str, int], stop_reason: str | None = None) -> None:
        print(f"\nSession stopped early: {stop_reason}" if stop_reason else "\nSession over")
        for name, final in final_bankrolls.items():
            start = self._start_bankrolls[name]
            print(f"  {name}: {start} -> {final} ({final - start:+})")
