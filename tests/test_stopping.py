"""Stopping a session: a player leaving (place_bet returns None) or Ctrl+C."""

import json

import pytest

from blackjack.api import Action, PlayerLeft
from blackjack.cards import StackedShoe
from blackjack.players import Player
from blackjack.session_log import SessionLog
from blackjack.table import Table
from blackjack.watchers import TerminalPrinter


class Scripted(Player):
    """Follows a script of bets and actions. A bet of None leaves; the string
    "interrupt" in either script simulates Ctrl+C at that moment."""

    def __init__(self, name, bets, actions=()):
        super().__init__(name)
        self.bets = list(bets)
        self.actions = list(actions)
        self.rounds_finished = 0

    def place_bet(self, view):
        bet = self.bets.pop(0)
        if bet == "interrupt":
            raise KeyboardInterrupt
        return bet

    def decide(self, view):
        action = self.actions.pop(0)
        if action == "interrupt":
            raise KeyboardInterrupt
        return action

    def round_over(self, result):
        self.rounds_finished += 1


def read_log(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_leaving_at_the_bet_prompt_ends_the_session(tmp_path):
    # Round 1: Bot bets 10, 10+9=19 stands; Human bets 10, 10+8=18 stands; dealer 10+7=17.
    # Round 2: Bot bets 10 first, then Human leaves -> round cancelled, Bot's bet returned.
    shoe = StackedShoe(["10", "10", "10", "9", "8", "7"])
    bot = Scripted("Bot", [10, 10], [Action.STAND])
    human = Scripted("Human", [10, None], [Action.STAND])
    path = tmp_path / "s.jsonl"
    table = Table(shoe=shoe, watchers=[SessionLog(path)])
    table.sit(bot, 100)
    table.sit(human, 100)
    table.play_session(10)

    assert table.bankroll("Bot") == 110  # won round 1; round 2 bet returned
    assert table.bankroll("Human") == 110
    records = read_log(path)
    assert [r["event"] for r in records] == [
        "session_start", "decision", "decision", "round", "round_cancelled", "session_end",
    ]
    end = records[-1]
    assert end["stopped_early"] == "Human left the table"
    assert end["rounds"] == 1
    for stats in end["players"].values():
        assert stats["net"] == stats["final_bankroll"] - stats["start_bankroll"]


def test_ctrl_c_mid_hand_after_a_split_restores_bankrolls(tmp_path):
    # Round 1: 8,8 vs dealer 6; split (bankroll now 80), then Ctrl+C on the first split hand.
    shoe = StackedShoe(["8", "6", "8", "10", "3", "4"])
    player = Scripted("P", [10], [Action.SPLIT, "interrupt"])
    path = tmp_path / "s.jsonl"
    table = Table(shoe=shoe, watchers=[SessionLog(path)])
    table.sit(player, 100)
    table.play_session(5)  # returns normally; the interrupt doesn't escape

    assert table.bankroll("P") == 100
    assert player.rounds_finished == 0
    records = read_log(path)
    assert [r["event"] for r in records] == ["session_start", "decision", "round_cancelled", "session_end"]
    assert records[-1]["stopped_early"] == "interrupted"
    assert records[-1]["players"]["P"]["final_bankroll"] == 100


def test_ctrl_c_at_a_bet_keeps_earlier_rounds(tmp_path):
    shoe = StackedShoe(["10", "10", "9", "7"])
    player = Scripted("P", [10, "interrupt"], [Action.STAND])
    table = Table(shoe=shoe, watchers=[SessionLog(tmp_path / "s.jsonl")])
    table.sit(player, 100)
    table.play_session(5)
    assert table.bankroll("P") == 110  # round 1 win is kept
    assert player.rounds_finished == 1


def test_printer_reports_the_early_stop(capsys):
    table = Table(shoe=StackedShoe([]), watchers=[TerminalPrinter()])
    table.sit(Scripted("P", [None]), 100)
    table.play_session(3)
    out = capsys.readouterr().out
    assert "Round 1 cancelled; bets returned" in out
    assert "Session stopped early: P left the table" in out
    assert "P: 100 -> 100 (+0)" in out


def test_play_round_alone_raises_and_restores():
    # Outside a session, leaving raises PlayerLeft, after undoing the bets already placed.
    bot = Scripted("Bot", [30])
    table = Table(shoe=StackedShoe([]))
    table.sit(bot, 100)
    table.sit(Scripted("Human", [None]), 100)
    with pytest.raises(PlayerLeft):
        table.play_round()
    assert table.bankroll("Bot") == 100
