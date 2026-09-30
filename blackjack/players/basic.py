"""Basic strategy: the mathematically best play for every hand.

The tables are for the default rules: 6 decks, the dealer stands on soft 17,
double after split, late surrender. With the dealer hitting soft 17, a few
close plays change, so treat this as slightly approximate under that rule.
"""

from blackjack.api import Action, BettingView, DecisionView
from blackjack.players.base import Player


def basic_strategy(view: DecisionView) -> Action:
    """The basic-strategy action for this view. Always one of view.legal_actions."""
    upcard = view.dealer_upcard
    dealer = 11 if upcard.rank == "A" else upcard.value  # 2..11
    legal = view.legal_actions
    cards = view.my_cards

    is_pair = len(cards) == 2 and cards[0].value == cards[1].value
    if is_pair and Action.SPLIT in legal and _should_split(cards[0].value, dealer):
        return Action.SPLIT

    total = view.my_total
    if Action.SURRENDER in legal and not view.is_soft:
        if (total == 16 and dealer >= 9) or (total == 15 and dealer == 10):
            return Action.SURRENDER

    play = _soft_play(total, dealer) if view.is_soft else _hard_play(total, dealer)
    if play == "double":
        return Action.DOUBLE if Action.DOUBLE in legal else Action.HIT
    if play == "double or stand":
        return Action.DOUBLE if Action.DOUBLE in legal else Action.STAND
    return Action.HIT if play == "hit" else Action.STAND


def _should_split(card_value: int, dealer: int) -> bool:
    if card_value in (1, 8):  # aces and eights: always
        return True
    if card_value == 9:
        return dealer not in (7, 10, 11)
    if card_value in (2, 3, 7):
        return dealer <= 7
    if card_value == 6:
        return dealer <= 6
    if card_value == 4:
        return dealer in (5, 6)
    return False  # fives and tens: never


def _hard_play(total: int, dealer: int) -> str:
    if total <= 8:
        return "hit"
    if total == 9:
        return "double" if 3 <= dealer <= 6 else "hit"
    if total == 10:
        return "double" if dealer <= 9 else "hit"
    if total == 11:
        return "double" if dealer <= 10 else "hit"
    if total == 12:
        return "stand" if 4 <= dealer <= 6 else "hit"
    if total <= 16:
        return "stand" if dealer <= 6 else "hit"
    return "stand"


def _soft_play(total: int, dealer: int) -> str:
    if total >= 19:
        return "stand"
    if total == 18:
        if 3 <= dealer <= 6:
            return "double or stand"
        return "stand" if dealer in (2, 7, 8) else "hit"
    if total == 17:
        return "double" if 3 <= dealer <= 6 else "hit"
    if total >= 15:
        return "double" if 4 <= dealer <= 6 else "hit"
    if total >= 13:
        return "double" if 5 <= dealer <= 6 else "hit"
    return "hit"


class BasicStrategyPlayer(Player):
    """Always plays basic strategy and bets a fixed amount (the table minimum by default)."""

    def __init__(self, name: str, bet: int | None = None):
        super().__init__(name)
        self.bet = bet

    def place_bet(self, view: BettingView) -> int:
        return self.bet if self.bet is not None else view.min_bet

    def decide(self, view: DecisionView) -> Action:
        return basic_strategy(view)
