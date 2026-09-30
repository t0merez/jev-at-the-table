"""A blackjack hand. Used inside the table only; players see views instead."""

from blackjack.cards import Card


class Hand:
    def __init__(self, bet: int = 0, cards: list[Card] | None = None, from_split: bool = False):
        self.cards: list[Card] = list(cards or [])
        self.bet = bet
        self.from_split = from_split
        self.surrendered = False
        self.finished = False

    def add(self, card: Card) -> None:
        self.cards.append(card)

    @property
    def _hard_total(self) -> int:
        return sum(card.value for card in self.cards)

    @property
    def is_soft(self) -> bool:
        """True when an ace is counted as 11."""
        return any(card.rank == "A" for card in self.cards) and self._hard_total + 10 <= 21

    @property
    def total(self) -> int:
        return self._hard_total + 10 if self.is_soft else self._hard_total

    @property
    def is_blackjack(self) -> bool:
        """21 on the first two cards. A split hand can't be a blackjack."""
        return len(self.cards) == 2 and self.total == 21 and not self.from_split

    @property
    def is_bust(self) -> bool:
        return self.total > 21

    @property
    def is_pair(self) -> bool:
        return len(self.cards) == 2 and self.cards[0].value == self.cards[1].value

    def __str__(self) -> str:
        return " ".join(str(card) for card in self.cards) + f" ({self.total})"
