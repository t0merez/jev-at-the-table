"""Cards and the shoe they are dealt from."""

import random
from dataclasses import dataclass

RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
SUITS = ("♠", "♥", "♦", "♣")


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str = "♠"

    @property
    def value(self) -> int:
        """Blackjack value. Aces count 1 here; a Hand decides when an ace counts 11."""
        if self.rank == "A":
            return 1
        if self.rank in ("J", "Q", "K"):
            return 10
        return int(self.rank)

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"


class Shoe:
    """Several shuffled decks. Reshuffled between rounds once it runs low."""

    def __init__(self, num_decks: int = 6, rng: random.Random | None = None, penetration: float = 0.75):
        self.num_decks = num_decks
        self._rng = rng or random.Random()
        self._reshuffle_below = int(52 * num_decks * (1 - penetration))
        self._cards: list[Card] = []
        self.shuffle()

    def shuffle(self) -> None:
        self._cards = [Card(rank, suit) for _ in range(self.num_decks) for suit in SUITS for rank in RANKS]
        self._rng.shuffle(self._cards)

    def shuffle_if_low(self) -> None:
        """Called by the table before each round, like a casino's cut card."""
        if len(self._cards) < self._reshuffle_below:
            self.shuffle()

    def draw(self) -> Card:
        if not self._cards:  # safety net; the cut card should prevent this
            self.shuffle()
        return self._cards.pop()


class StackedShoe(Shoe):
    """A shoe that deals the given cards in order, for tests and demos.

    Each round is dealt in this order: every player's first card, the dealer's
    up card, every player's second card, the dealer's hole card, then any
    hits in the order they are asked for.
    """

    def __init__(self, cards: list[str | Card]):
        # Stored reversed so that pop() returns the first card.
        self._cards = [c if isinstance(c, Card) else Card(c) for c in reversed(cards)]

    def shuffle_if_low(self) -> None:
        pass

    def draw(self) -> Card:
        if not self._cards:
            raise RuntimeError("The stacked shoe ran out of cards")
        return self._cards.pop()
