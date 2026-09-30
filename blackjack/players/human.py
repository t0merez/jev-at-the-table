"""A human playing from the terminal."""

from blackjack.api import Action, BettingView, DecisionView, RoundResult
from blackjack.players.base import Player

KEYS = {"h": Action.HIT, "s": Action.STAND, "d": Action.DOUBLE, "p": Action.SPLIT, "r": Action.SURRENDER}


def _cards(cards) -> str:
    return " ".join(str(card) for card in cards)


class HumanPlayer(Player):
    def place_bet(self, view: BettingView) -> int:
        highest = view.bankroll if view.max_bet is None else min(view.bankroll, view.max_bet)
        while True:
            text = input(f"\n{self.name}, you have {view.bankroll}. Your bet ({view.min_bet}-{highest}): ")
            if text.strip().isdigit() and view.min_bet <= int(text) <= highest:
                return int(text)
            print(f"Please enter a whole number from {view.min_bet} to {highest}.")

    def decide(self, view: DecisionView) -> Action:
        print(f"\nDealer shows {view.dealer_upcard}")
        for other in view.other_players_cards:
            print(f"  Other hand: {_cards(other)}")
        which = f" (hand {view.hand_index + 1} of {view.num_hands})" if view.num_hands > 1 else ""
        soft = "soft " if view.is_soft else ""
        print(f"{self.name}, your hand{which}: {_cards(view.my_cards)} = {soft}{view.my_total}, bet {view.bet}")

        options = "  ".join(f"[{key}] {action.value}" for key, action in KEYS.items() if action in view.legal_actions)
        while True:
            key = input(f"{options}: ").strip().lower()
            if key in KEYS and KEYS[key] in view.legal_actions:
                return KEYS[key]
            print("Please choose one of the options shown.")

    def round_over(self, result: RoundResult) -> None:
        print(f"\nDealer: {_cards(result.dealer_cards)} = {result.dealer_total}")
        for hand in result.hands:
            print(f"  Your hand: {_cards(hand.cards)} -> {hand.outcome.value} ({hand.net:+})")
        print(f"  {self.name}, you now have {result.bankroll_after}")
