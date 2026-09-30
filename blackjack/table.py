"""The blackjack table. It owns the cards and the chips and runs the game.

Players only ever see the read-only views from blackjack.api, and answer with
a bet or an Action. The table checks every answer.

House rules that aren't options in TableRules: the dealer peeks for
blackjack, split aces get one card each, and a hand that reaches 21 stands
automatically.
"""

from types import MappingProxyType

from blackjack.api import (
    Action,
    BettingView,
    DecisionView,
    HandResult,
    IllegalActionError,
    InvalidBetError,
    Outcome,
    RoundResult,
)
from blackjack.cards import Shoe
from blackjack.hand import Hand
from blackjack.players.base import Player
from blackjack.rules import TableRules
from blackjack.watchers import SeatInfo, TableWatcher


class Seat:
    """A player's place at the table: the player, its chips and its hands.
    Internal to the table; players never see their seat."""

    def __init__(self, player: Player, bankroll: int):
        self.player = player
        self.bankroll = bankroll
        self.hands: list[Hand] = []


class Table:
    def __init__(self, rules: TableRules | None = None, shoe: Shoe | None = None, watchers: list[TableWatcher] = ()):
        self.rules = rules or TableRules()
        self.shoe = shoe or Shoe(self.rules.num_decks)
        self.watchers = list(watchers)  # e.g. a SessionLog and a TerminalPrinter
        self._seats: list[Seat] = []
        self._playing: list[Seat] = []  # seats with a bet in the current round
        self._dealer = Hand()
        self._round_no = 0

    def sit(self, player: Player, bankroll: int) -> None:
        if any(seat.player.name == player.name for seat in self._seats):
            raise ValueError(f"A player named {player.name!r} is already seated")
        if bankroll < 0:
            raise ValueError("bankroll can't be negative")
        self._seats.append(Seat(player, bankroll))

    def bankroll(self, name: str) -> int:
        return next(seat.bankroll for seat in self._seats if seat.player.name == name)

    # ----- sessions and rounds -----

    def play_session(self, num_rounds: int) -> None:
        """Play up to num_rounds rounds, stopping early if nobody can afford the minimum bet."""
        seats = tuple(SeatInfo(seat.player.name, type(seat.player).__name__, seat.bankroll) for seat in self._seats)
        for watcher in self.watchers:
            watcher.start(self.rules, seats)
        for _ in range(num_rounds):
            if not any(seat.bankroll >= self.rules.min_bet for seat in self._seats):
                break
            self.play_round()
        final_bankrolls = MappingProxyType({seat.player.name: seat.bankroll for seat in self._seats})
        for watcher in self.watchers:
            watcher.end(final_bankrolls)

    def play_round(self) -> dict[str, RoundResult]:
        """Play one round and return each participating player's result, by name."""
        self._round_no += 1
        self.shoe.shuffle_if_low()

        self._playing = self._take_bets()
        if not self._playing:
            return {}
        self._deal()
        if not self._dealer.is_blackjack:  # on dealer blackjack, the round ends at once
            for seat in self._playing:
                self._play_turn(seat)
            self._play_dealer()

        results = {seat.player.name: self._settle(seat) for seat in self._playing}
        read_only_results = MappingProxyType(results)
        for watcher in self.watchers:
            watcher.round_end(self._round_no, tuple(self._dealer.cards), self._dealer.total, read_only_results)
        for seat in self._playing:
            seat.player.round_over(results[seat.player.name])
        return results

    # ----- round steps -----

    def _take_bets(self) -> list[Seat]:
        playing = []
        for seat in self._seats:
            seat.hands = []
            if seat.bankroll < self.rules.min_bet:
                continue  # can't afford to play; sits this round out
            bet = seat.player.place_bet(BettingView(seat.bankroll, self.rules.min_bet, self.rules.max_bet))
            self._check_bet(seat, bet)
            seat.bankroll -= bet
            seat.hands = [Hand(bet)]
            playing.append(seat)
        return playing

    def _check_bet(self, seat: Seat, bet: int) -> None:
        name = seat.player.name
        if not isinstance(bet, int) or isinstance(bet, bool):
            raise InvalidBetError(f"{name} bet {bet!r}; bets must be whole numbers")
        if bet < self.rules.min_bet:
            raise InvalidBetError(f"{name} bet {bet}, below the table minimum of {self.rules.min_bet}")
        if self.rules.max_bet is not None and bet > self.rules.max_bet:
            raise InvalidBetError(f"{name} bet {bet}, above the table maximum of {self.rules.max_bet}")
        if bet > seat.bankroll:
            raise InvalidBetError(f"{name} bet {bet} but only has {seat.bankroll}")

    def _deal(self) -> None:
        self._dealer = Hand()
        for _ in range(2):
            for seat in self._playing:
                seat.hands[0].add(self.shoe.draw())
            self._dealer.add(self.shoe.draw())

    def _play_turn(self, seat: Seat) -> None:
        index = 0
        while index < len(seat.hands):  # a split adds hands while we loop
            self._play_hand(seat, index)
            index += 1

    def _play_hand(self, seat: Seat, index: int) -> None:
        hand = seat.hands[index]
        while not hand.finished:
            if hand.total >= 21:  # blackjack, 21 or bust: nothing to decide
                hand.finished = True
                break
            view = self._decision_view(seat, index)
            action = seat.player.decide(view)
            if action not in view.legal_actions:
                raise IllegalActionError(
                    f"{seat.player.name} chose {action!r}; legal actions were {[a.value for a in view.legal_actions]}"
                )
            for watcher in self.watchers:
                watcher.decision(self._round_no, seat.player.name, view, action)
            self._apply(seat, index, action)

    def _apply(self, seat: Seat, index: int, action: Action) -> None:
        hand = seat.hands[index]
        if action is Action.HIT:
            hand.add(self.shoe.draw())
        elif action is Action.STAND:
            hand.finished = True
        elif action is Action.DOUBLE:
            seat.bankroll -= hand.bet
            hand.bet *= 2
            hand.add(self.shoe.draw())
            hand.finished = True
        elif action is Action.SURRENDER:
            hand.surrendered = True
            hand.finished = True
        elif action is Action.SPLIT:
            seat.bankroll -= hand.bet
            new_hand = Hand(hand.bet, [hand.cards.pop()], from_split=True)
            hand.from_split = True
            hand.add(self.shoe.draw())
            new_hand.add(self.shoe.draw())
            seat.hands.insert(index + 1, new_hand)
            if new_hand.cards[0].rank == "A":  # split aces get one card each
                hand.finished = new_hand.finished = True

    def _legal_actions(self, seat: Seat, hand: Hand) -> tuple[Action, ...]:
        """The one place that decides what a player may do."""
        actions = [Action.HIT, Action.STAND]
        first_two_cards = len(hand.cards) == 2
        can_match_bet = seat.bankroll >= hand.bet
        if first_two_cards and can_match_bet and (not hand.from_split or self.rules.double_after_split):
            actions.append(Action.DOUBLE)
        if hand.is_pair and can_match_bet and len(seat.hands) < self.rules.max_hands:
            actions.append(Action.SPLIT)
        if first_two_cards and self.rules.allow_surrender and not hand.from_split:
            actions.append(Action.SURRENDER)
        return tuple(actions)

    def _decision_view(self, seat: Seat, index: int) -> DecisionView:
        hand = seat.hands[index]
        return DecisionView(
            my_cards=tuple(hand.cards),
            my_total=hand.total,
            is_soft=hand.is_soft,
            hand_index=index,
            num_hands=len(seat.hands),
            bet=hand.bet,
            dealer_upcard=self._dealer.cards[0],
            legal_actions=self._legal_actions(seat, hand),
            bankroll=seat.bankroll,
            other_players_cards=tuple(
                tuple(other_hand.cards) for other in self._playing if other is not seat for other_hand in other.hands
            ),
        )

    def _play_dealer(self) -> None:
        hands = [hand for seat in self._playing for hand in seat.hands]
        if all(hand.is_bust or hand.surrendered or hand.is_blackjack for hand in hands):
            return  # nothing left for the dealer to beat
        dealer = self._dealer
        while dealer.total < 17 or (dealer.total == 17 and dealer.is_soft and self.rules.dealer_hits_soft_17):
            dealer.add(self.shoe.draw())

    def _settle(self, seat: Seat) -> RoundResult:
        hand_results = []
        for hand in seat.hands:
            outcome, returned = self._outcome(hand)
            seat.bankroll += returned
            hand_results.append(HandResult(tuple(hand.cards), hand.bet, outcome, returned - hand.bet))
        return RoundResult(tuple(self._dealer.cards), self._dealer.total, tuple(hand_results), seat.bankroll)

    def _outcome(self, hand: Hand) -> tuple[Outcome, int]:
        """Return the outcome and the chips handed back to the player (stake included)."""
        dealer = self._dealer
        if hand.surrendered:
            return Outcome.SURRENDER, hand.bet // 2
        if hand.is_bust:
            return Outcome.LOSE, 0
        if dealer.is_blackjack:
            return (Outcome.PUSH, hand.bet) if hand.is_blackjack else (Outcome.LOSE, 0)
        if hand.is_blackjack:
            numerator, denominator = self.rules.blackjack_pays
            return Outcome.BLACKJACK, hand.bet + hand.bet * numerator // denominator
        if dealer.is_bust or hand.total > dealer.total:
            return Outcome.WIN, 2 * hand.bet
        if hand.total == dealer.total:
            return Outcome.PUSH, hand.bet
        return Outcome.LOSE, 0
