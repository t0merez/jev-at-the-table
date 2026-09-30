"""Table rules: bet limits and rule options."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TableRules:
    min_bet: int = 1
    max_bet: int | None = None  # None means no limit
    num_decks: int = 6
    dealer_hits_soft_17: bool = False
    blackjack_pays: tuple[int, int] = (3, 2)
    allow_surrender: bool = True  # late surrender, on the first two cards only
    double_after_split: bool = True
    max_hands: int = 4  # how many hands a player can split into

    def __post_init__(self):
        if self.min_bet < 1:
            raise ValueError("min_bet must be at least 1")
        if self.max_bet is not None and self.max_bet < self.min_bet:
            raise ValueError("max_bet can't be lower than min_bet")
