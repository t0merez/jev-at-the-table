"""Jev, TypeSafe's System One model, as a blackjack player.

Each decision is one Choice question whose options are the legal actions.
Following the jev-1.13 guidance, the arithmetic stays in code (Jev is told
"hard 16", not asked to add cards up) and the state holds only what the
decision needs.
"""

from dataclasses import dataclass

from blackjack.api import Action, BettingView, DecisionView
from blackjack.cards import Card
from blackjack.players.base import Player

INSTRUCTIONS = (
    "You are playing blackjack against the dealer. Choose the action for my_hand "
    "that wins the most money on average, given the dealer's up card."
)

ACTION_DESCRIPTIONS = {
    Action.HIT: "Take one more card.",
    Action.STAND: "Take no more cards and keep the current total.",
    Action.DOUBLE: "Double the bet, take exactly one more card, then stop.",
    Action.SPLIT: "Split the pair into two separate hands, each with its own bet.",
    Action.SURRENDER: "Give up the hand now and lose half the bet.",
}

CARD_NAMES = {"A": "ace", "J": "jack", "Q": "queen", "K": "king"}


@dataclass(frozen=True)
class JevDecision:
    """One decision, kept for later analysis."""

    view: DecisionView
    action: Action
    probabilities: dict[str, float]
    confidence: float


class JevPlayer(Player):
    def __init__(self, name: str = "Jev", bet: int | None = None, client=None, model: str | None = None):
        super().__init__(name)
        self.bet = bet
        if client is None:
            try:  # imported here so the SDK is only needed for Jev
                from typesafe_sdk import TypeSafeClient
            except ImportError as error:
                raise ImportError("JevPlayer needs the TypeSafe SDK: pip install typesafe-sdk") from error
            client = TypeSafeClient(model=model)  # reads TYPESAFE_API_KEY from the environment
        self._client = client
        self.decisions: list[JevDecision] = []

    def place_bet(self, view: BettingView) -> int:
        return self.bet if self.bet is not None else view.min_bet

    def decide(self, view: DecisionView) -> Action:
        question = {
            "type": "choice",
            "instructions": INSTRUCTIONS,
            "criteria": {action.value: ACTION_DESCRIPTIONS[action] for action in view.legal_actions},
        }
        response = self._client.system_one(state=self._state(view), questions={"action": question})
        answer = response.choices["action"]
        action = Action(answer.choice)
        self.decisions.append(JevDecision(view, action, dict(answer.probabilities), answer.confidence))
        return action

    @staticmethod
    def _state(view: DecisionView) -> dict:
        kind = "soft" if view.is_soft else "hard"
        hand = {
            "cards": [_card_name(card) for card in view.my_cards],
            "total": f"{kind} {view.my_total}",
        }
        cards = view.my_cards
        if len(cards) == 2 and cards[0].value == cards[1].value:
            hand["pair"] = f"a pair of {_card_name(cards[0])}s"
        if view.num_hands > 1:
            hand["note"] = "This hand came from a split."
        return {"my_hand": hand, "dealer_up_card": _card_name(view.dealer_upcard)}


def _card_name(card: Card) -> str:
    return CARD_NAMES.get(card.rank, card.rank)
