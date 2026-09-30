import pytest

from blackjack.api import Action, DecisionView
from blackjack.cards import Card
from blackjack.hand import Hand
from blackjack.players import basic_strategy

ALL = (Action.HIT, Action.STAND, Action.DOUBLE, Action.SPLIT, Action.SURRENDER)


def view(my_ranks, dealer_rank, legal=ALL):
    hand = Hand(cards=[Card(r) for r in my_ranks])
    return DecisionView(
        my_cards=tuple(hand.cards),
        my_total=hand.total,
        is_soft=hand.is_soft,
        hand_index=0,
        num_hands=1,
        bet=10,
        dealer_upcard=Card(dealer_rank),
        legal_actions=legal,
        bankroll=100,
        other_players_cards=(),
    )


@pytest.mark.parametrize(
    "mine, dealer, expected",
    [
        (["10", "6"], "10", Action.SURRENDER),
        (["10", "6"], "6", Action.STAND),
        (["10", "2"], "3", Action.HIT),
        (["6", "5"], "10", Action.DOUBLE),
        (["6", "5"], "A", Action.HIT),
        (["A", "7"], "2", Action.STAND),
        (["A", "7"], "9", Action.HIT),
        (["A", "7"], "4", Action.DOUBLE),
        (["8", "8"], "10", Action.SPLIT),
        (["10", "10"], "6", Action.STAND),
        (["9", "9"], "7", Action.STAND),
        (["5", "5"], "6", Action.DOUBLE),
    ],
)
def test_basic_strategy(mine, dealer, expected):
    assert basic_strategy(view(mine, dealer)) is expected


def test_falls_back_when_double_is_not_allowed():
    hit_stand = (Action.HIT, Action.STAND)
    assert basic_strategy(view(["6", "5"], "6", hit_stand)) is Action.HIT
    assert basic_strategy(view(["A", "7"], "4", hit_stand)) is Action.STAND
