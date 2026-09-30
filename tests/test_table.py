"""Table tests with stacked shoes, so every card is known in advance.

Deal order reminder: each player's first card, dealer up card, each player's
second card, dealer hole card, then hits in play order.
"""

import json

import pytest

from blackjack.api import Action, IllegalActionError, InvalidBetError, Outcome
from blackjack.cards import StackedShoe
from blackjack.players import BasicStrategyPlayer, Player
from blackjack.rules import TableRules
from blackjack.session_log import SessionLog
from blackjack.table import Table
from blackjack.watchers import TerminalPrinter


class ScriptedPlayer(Player):
    """Bets a fixed amount and plays a fixed list of actions."""

    def __init__(self, name, bet=10, actions=()):
        super().__init__(name)
        self.bet = bet
        self.actions = list(actions)
        self.views = []
        self.results = []

    def place_bet(self, view):
        return self.bet

    def decide(self, view):
        self.views.append(view)
        return self.actions.pop(0)

    def round_over(self, result):
        self.results.append(result)


def one_player_table(cards, actions=(), bet=10, bankroll=100, rules=None):
    player = ScriptedPlayer("P", bet, actions)
    table = Table(rules or TableRules(), StackedShoe(cards))
    table.sit(player, bankroll)
    return table, player


def only_hand(results, name="P"):
    (hand,) = results[name].hands
    return hand


# ----- bets -----


@pytest.mark.parametrize("bet", [4, 101, 7.5, True])
def test_invalid_bets_are_rejected(bet):
    table, _ = one_player_table([], bet=bet, rules=TableRules(min_bet=5, max_bet=500))
    with pytest.raises(InvalidBetError):
        table.play_round()


def test_bet_above_bankroll_is_rejected():
    table, _ = one_player_table([], bet=200, bankroll=100)
    with pytest.raises(InvalidBetError):
        table.play_round()


def test_any_whole_bet_is_allowed_without_limits():
    table, _ = one_player_table(["10", "9", "10", "8"], [Action.STAND], bet=12345, bankroll=20000)
    assert only_hand(table.play_round()).net == 12345


def test_player_who_cannot_afford_minimum_sits_out():
    table, player = one_player_table([], bankroll=4, rules=TableRules(min_bet=5))
    assert table.play_round() == {}
    assert player.views == []


# ----- blackjacks -----


def test_blackjack_pays_3_to_2():
    table, _ = one_player_table(["A", "9", "K", "8"], bet=10)
    hand = only_hand(table.play_round())
    assert (hand.outcome, hand.net) == (Outcome.BLACKJACK, 15)
    assert table.bankroll("P") == 115


def test_blackjack_payout_on_odd_bet_rounds_down():
    table, _ = one_player_table(["A", "9", "K", "8"], bet=5)
    assert only_hand(table.play_round()).net == 7


def test_blackjack_pushes_against_dealer_blackjack():
    table, _ = one_player_table(["A", "A", "K", "K"])
    hand = only_hand(table.play_round())
    assert (hand.outcome, hand.net) == (Outcome.PUSH, 0)


def test_dealer_blackjack_ends_round_without_decisions():
    table, player = one_player_table(["10", "A", "9", "K"])
    hand = only_hand(table.play_round())
    assert (hand.outcome, hand.net) == (Outcome.LOSE, -10)
    assert player.views == []


# ----- actions -----


def test_hit_until_bust_loses():
    table, _ = one_player_table(["10", "9", "6", "8", "K"], [Action.HIT])
    hand = only_hand(table.play_round())
    assert (hand.outcome, hand.net) == (Outcome.LOSE, -10)


def test_double_doubles_the_bet_and_takes_one_card():
    # Player 6+5=11, doubles, gets 10 = 21. Dealer 10+7 = 17.
    table, _ = one_player_table(["6", "10", "5", "7", "10"], [Action.DOUBLE])
    hand = only_hand(table.play_round())
    assert (hand.bet, hand.outcome, hand.net) == (20, Outcome.WIN, 20)


def test_surrender_returns_half_the_bet():
    table, _ = one_player_table(["10", "10", "6", "8"], [Action.SURRENDER])
    hand = only_hand(table.play_round())
    assert (hand.outcome, hand.net) == (Outcome.SURRENDER, -5)


def test_split_makes_two_hands_with_their_own_bets():
    # 8,8 vs dealer 6; split. Hand 1: 8+3=11, stand. Hand 2: 8+10=18, stand.
    # Dealer 6+10=16, hits 9 -> bust.
    cards = ["8", "6", "8", "10", "3", "10", "9"]
    table, player = one_player_table(cards, [Action.SPLIT, Action.STAND, Action.STAND])
    results = table.play_round()
    assert [h.net for h in results["P"].hands] == [10, 10]
    assert table.bankroll("P") == 120
    assert [v.hand_index for v in player.views[1:]] == [0, 1]
    assert player.views[1].num_hands == 2


def test_split_aces_get_one_card_each():
    # A,A vs dealer 9+8=17. Split: A+K=21 and A+9=20, no more decisions.
    cards = ["A", "9", "A", "8", "K", "9"]
    table, player = one_player_table(cards, [Action.SPLIT])
    results = table.play_round()
    # 21 after a split is a win, not a blackjack.
    assert [h.outcome for h in results["P"].hands] == [Outcome.WIN, Outcome.WIN]
    assert len(player.views) == 1


def test_illegal_action_is_rejected():
    table, _ = one_player_table(["10", "9", "7", "8"], [Action.SPLIT])
    with pytest.raises(IllegalActionError):
        table.play_round()


def test_no_double_or_surrender_after_hitting():
    table, player = one_player_table(["2", "10", "3", "7", "4", "10"], [Action.HIT, Action.STAND])
    table.play_round()
    assert player.views[1].legal_actions == (Action.HIT, Action.STAND)


# ----- dealer -----


@pytest.mark.parametrize("hits_soft_17, dealer_total", [(False, 17), (True, 20)])
def test_dealer_soft_17_rule(hits_soft_17, dealer_total):
    # Dealer A+6 = soft 17. If it hits, it draws a 3 -> 20.
    table, _ = one_player_table(["10", "A", "8", "6", "3"], [Action.STAND], rules=TableRules(dealer_hits_soft_17=hits_soft_17))
    assert table.play_round()["P"].dealer_total == dealer_total


# ----- several players -----


def test_two_players_share_a_dealer_and_see_each_other():
    # Alice 10+9=19, Bob 10+7=17, dealer 10+8=18.
    table = Table(shoe=StackedShoe(["10", "10", "10", "9", "7", "8"]))
    alice = ScriptedPlayer("Alice", 10, [Action.STAND])
    bob = ScriptedPlayer("Bob", 20, [Action.STAND])
    table.sit(alice, 100)
    table.sit(bob, 100)
    results = table.play_round()
    assert only_hand(results, "Alice").net == 10
    assert only_hand(results, "Bob").net == -20
    assert [str(c) for c in bob.views[0].other_players_cards[0]] == ["10♠", "9♠"]
    assert alice.results[0].dealer_total == 18


def test_duplicate_names_are_rejected():
    table = Table()
    table.sit(ScriptedPlayer("P"), 100)
    with pytest.raises(ValueError):
        table.sit(ScriptedPlayer("P"), 100)


# ----- session log -----


def test_session_log_records_every_round_and_balances(tmp_path):
    path = tmp_path / "session.jsonl"
    table = Table(watchers=[SessionLog(path)])
    table.sit(BasicStrategyPlayer("A"), 1000)
    table.sit(BasicStrategyPlayer("B", bet=25), 1000)
    table.play_session(50)

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert records[0]["event"] == "session_start"
    assert records[-1]["event"] == "session_end"
    assert sum(r["event"] == "round" for r in records) == 50
    assert any(r["event"] == "decision" for r in records)

    for name, stats in records[-1]["players"].items():
        assert stats["net"] == stats["final_bankroll"] - stats["start_bankroll"]
        assert stats["final_bankroll"] == table.bankroll(name)


def test_terminal_printer_shows_decisions_and_summary(capsys):
    # Alice 10+6=16 vs dealer 10: hits a 3 -> 19, stands. Dealer 10+8=18.
    table = Table(shoe=StackedShoe(["10", "10", "6", "8", "3"]), watchers=[TerminalPrinter()])
    table.sit(ScriptedPlayer("Alice", 10, [Action.HIT, Action.STAND]), 100)
    table.play_session(1)
    out = capsys.readouterr().out
    assert "Round 1, dealer shows 10♠" in out
    assert "Alice: 10♠ 6♠ (16) -> hit" in out
    assert "Alice: 10♠ 6♠ 3♠ -> win (+10), bankroll 110" in out
    assert "Alice: 100 -> 110 (+10)" in out
