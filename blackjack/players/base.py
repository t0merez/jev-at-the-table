"""The interface every player type implements."""

from abc import ABC, abstractmethod

from blackjack.api import Action, BettingView, DecisionView, RoundResult


class Player(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def place_bet(self, view: BettingView) -> int | None:
        """Return a whole-number bet within the limits in the view, or None to leave the table."""

    @abstractmethod
    def decide(self, view: DecisionView) -> Action:
        """Return one of view.legal_actions."""

    def round_over(self, result: RoundResult) -> None:
        """Called at the end of each round the player took part in. Optional."""
