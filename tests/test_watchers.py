"""Watchers only observe: they print or log, and can't change the game or reach players."""

import json
import random
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from blackjack.api import Action
from blackjack.cards import Shoe, StackedShoe
from blackjack.players import BasicStrategyPlayer, JevPlayer, basic_strategy
from blackjack.table import Table
from blackjack.watchers import SeatInfo, TableWatcher, TerminalPrinter


class RecordingBot(BasicStrategyPlayer):
    """Plays basic strategy and records everything the table shows it."""

    def __init__(self, name, bet=10):
        super().__init__(name, bet)
        self.seen = []

    def decide(self, view):
        self.seen.append(view)
        return super().decide(view)

    def round_over(self, result):
        self.seen.append(result)


class BasicStrategyClient:
    """A fake TypeSafe client that answers like basic strategy and records every request."""

    def __init__(self):
        self.requests = []
        self.view = None

    def system_one(self, state, questions):
        self.requests.append(state)
        action = basic_strategy(self.view).value
        answer = SimpleNamespace(choice=action, probabilities={action: 1.0}, confidence=1.0)
        return SimpleNamespace(choices={"action": answer})


class FakeJev(JevPlayer):
    """JevPlayer with the fake client; hands the fake the view so it can answer."""

    def __init__(self):
        super().__init__(client=BasicStrategyClient(), bet=10)

    def decide(self, view):
        self._client.view = view
        return super().decide(view)


def play(watchers, rounds=200, seed=11):
    """Two recording bots, a seeded shoe; returns the bots after the session."""
    alice, bob = RecordingBot("Alice"), RecordingBot("Bob", bet=25)
    table = Table(shoe=Shoe(6, random.Random(seed)), watchers=watchers)
    table.sit(alice, 10_000)
    table.sit(bob, 10_000)
    table.play_session(rounds)
    return table, alice, bob


# ----- hiding players -----


def test_printer_hides_the_named_player_and_the_dealer(capsys):
    # Human 10+6=16 hits a 3 -> 19. Bot 9+7=16 surrenders against the 10. Dealer 10+8=18.
    table = Table(
        shoe=StackedShoe(["10", "9", "10", "6", "7", "8", "3"]),
        watchers=[TerminalPrinter(hide_players=("Human",), show_dealer=False)],
    )
    human = RecordingBot("Human")
    human.decide = lambda view: Action.HIT if view.my_total < 17 else Action.STAND
    table.sit(human, 100)
    table.sit(BasicStrategyPlayer("Bot", 10), 100)
    table.play_session(1)
    out = capsys.readouterr().out

    assert "Bot: 9♠ 7♠ (16) -> surrender" in out
    assert "Bot: 9♠ 7♠ -> surrender (-5), bankroll 95" in out
    assert "Human: 10♠" not in out  # no decisions or results for the hidden player
    assert "Dealer:" not in out


def test_printer_shows_everyone_by_default(capsys):
    play([TerminalPrinter()], rounds=20)
    out = capsys.readouterr().out
    assert "  Alice: " in out and "  Bob: " in out and "Dealer: " in out


# ----- watchers can't change the game -----


def test_printer_and_log_do_not_change_the_game(tmp_path, capsys):
    from blackjack.session_log import SessionLog

    table_a, alice_a, bob_a = play([])
    table_b, alice_b, bob_b = play([TerminalPrinter(), SessionLog(tmp_path / "s.jsonl")])

    # Same cards, same views, same results, same money, with or without watchers.
    assert alice_a.seen == alice_b.seen
    assert bob_a.seen == bob_b.seen
    assert table_a.bankroll("Alice") == table_b.bankroll("Alice")
    assert table_a.bankroll("Bob") == table_b.bankroll("Bob")


class Vandal(TableWatcher):
    """A watcher that tries to change everything it's given."""

    def __init__(self):
        self.attempts = 0
        self.failures = 0

    def _try(self, change):
        self.attempts += 1
        try:
            change()
        except (TypeError, AttributeError, FrozenInstanceError):
            self.failures += 1

    def start(self, rules, seats):
        assert all(isinstance(seat, SeatInfo) for seat in seats)  # names only, no player objects
        self._try(lambda: setattr(rules, "min_bet", 0))
        self._try(lambda: setattr(seats[0], "bankroll", 1_000_000))

    def decision(self, round_no, player_name, view, action):
        self._try(lambda: setattr(view, "legal_actions", ()))

    def round_end(self, round_no, dealer_cards, dealer_total, results):
        self._try(lambda: dealer_cards.append(dealer_cards[0]))
        self._try(lambda: results.clear())
        self._try(lambda: setattr(next(iter(results.values())), "bankroll_after", 0))

    def end(self, final_bankrolls):
        self._try(lambda: final_bankrolls.update({"Alice": 0}))


def test_watchers_only_get_read_only_data():
    vandal = Vandal()
    table, alice, _ = play([vandal], rounds=50)
    assert vandal.attempts > 0
    assert vandal.failures == vandal.attempts  # every attempt to change something failed
    reference, alice_ref, _ = play([], rounds=50)
    assert alice.seen == alice_ref.seen
    assert table.bankroll("Alice") == reference.bankroll("Alice")


# ----- Jev doesn't see other players' hands -----


def test_jev_never_receives_other_players_cards(tmp_path, capsys):
    from blackjack.session_log import SessionLog

    jev = FakeJev()
    table = Table(shoe=Shoe(6, random.Random(3)), watchers=[TerminalPrinter(), SessionLog(tmp_path / "s.jsonl")])
    table.sit(BasicStrategyPlayer("Basic bot", 10), 10_000)  # sits first, so its hand is on the table
    table.sit(jev, 10_000)
    table.play_session(100)

    requests = jev._client.requests
    assert len(requests) == len(jev.decisions) > 0
    for state, decision in zip(requests, jev.decisions):
        assert set(state) == {"my_hand", "dealer_up_card"}
        assert len(state["my_hand"]["cards"]) == len(decision.view.my_cards)
        assert decision.view.other_players_cards  # the bot's hand was visible on the table...
        assert "other" not in json.dumps(state)  # ...but never sent to Jev
