"""JevPlayer tests with a fake client, so no API key or network is needed."""

from types import SimpleNamespace

from blackjack.api import Action
from blackjack.cards import StackedShoe
from blackjack.players.jev import JevPlayer
from blackjack.table import Table


class FakeClient:
    """Answers with the given choices in order and records the requests."""

    def __init__(self, *choices):
        self.choices = list(choices)
        self.requests = []

    def system_one(self, state, questions):
        self.requests.append((state, questions))
        choice = self.choices.pop(0)
        options = questions["action"]["criteria"]
        probabilities = {option: (0.9 if option == choice else 0.1 / (len(options) - 1)) for option in options}
        answer = SimpleNamespace(choice=choice, probabilities=probabilities, confidence=0.8)
        return SimpleNamespace(choices={"action": answer})


def test_jev_plays_a_round_through_the_table():
    client = FakeClient("stand")
    jev = JevPlayer(client=client)
    table = Table(shoe=StackedShoe(["10", "K", "6", "7"]))
    table.sit(jev, 100)
    table.play_round()

    state, questions = client.requests[0]
    assert state == {"my_hand": {"cards": ["10", "6"], "total": "hard 16"}, "dealer_up_card": "king"}
    assert list(questions["action"]["criteria"]) == ["hit", "stand", "double", "surrender"]
    assert jev.decisions[0].action is Action.STAND
    assert jev.decisions[0].confidence == 0.8
    assert table.bankroll("Jev") == 99  # bets the table minimum of 1; 16 loses to 17


def test_state_names_soft_totals_and_pairs():
    # 8,8 vs dealer ace; split into 8+A (soft 19) and 8+3 (hard 11), stand on both.
    client = FakeClient("split", "stand", "stand")
    table = Table(shoe=StackedShoe(["8", "A", "8", "6", "A", "3"]))
    table.sit(JevPlayer(client=client), 100)
    table.play_round()
    states = [state for state, _ in client.requests]
    assert states[0]["my_hand"] == {"cards": ["8", "8"], "total": "hard 16", "pair": "a pair of 8s"}
    assert states[0]["dealer_up_card"] == "ace"
    assert states[1]["my_hand"]["total"] == "soft 19"
    assert states[1]["my_hand"]["note"] == "This hand came from a split."
