"""The boundary between the table and its players.

Everything a player receives or returns is defined here. Views are frozen
snapshots: a player can read them but can't change the game through them.
"""

from dataclasses import dataclass
from enum import Enum

from blackjack.cards import Card


class Action(Enum):
    HIT = "hit"
    STAND = "stand"
    DOUBLE = "double"
    SPLIT = "split"
    SURRENDER = "surrender"


class Outcome(Enum):
    BLACKJACK = "blackjack"
    WIN = "win"
    PUSH = "push"
    LOSE = "lose"
    SURRENDER = "surrender"


class InvalidBetError(ValueError):
    """A player's bet broke the table limits or was more than its bankroll."""


class IllegalActionError(ValueError):
    """A player chose an action that isn't in legal_actions."""


class PlayerLeft(Exception):
    """Raised by the table when a player leaves (place_bet returned None). Ends the session."""

    def __init__(self, player_name: str):
        super().__init__(f"{player_name} left the table")
        self.player_name = player_name


@dataclass(frozen=True)
class BettingView:
    """What a player sees when asked for a bet."""

    bankroll: int
    min_bet: int
    max_bet: int | None  # None means no limit


@dataclass(frozen=True)
class DecisionView:
    """What a player sees when asked to act on one of its hands."""

    # This hand
    my_cards: tuple[Card, ...]
    my_total: int
    is_soft: bool
    hand_index: int  # which of the player's hands this is (0 unless split)
    num_hands: int
    bet: int
    # The table
    dealer_upcard: Card
    legal_actions: tuple[Action, ...]
    bankroll: int  # chips not already on the table
    other_players_cards: tuple[tuple[Card, ...], ...]  # every other hand in play


@dataclass(frozen=True)
class HandResult:
    cards: tuple[Card, ...]
    bet: int
    outcome: Outcome
    net: int  # chips won (positive) or lost (negative) on this hand


@dataclass(frozen=True)
class RoundResult:
    """What a player is told when a round ends."""

    dealer_cards: tuple[Card, ...]
    dealer_total: int
    hands: tuple[HandResult, ...]
    bankroll_after: int
