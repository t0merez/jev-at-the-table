"""Play blackjack in the terminal, or simulate basic strategy.

  python main.py                        you and a basic-strategy bot, 10 rounds
  python main.py --jev --rounds 50      Jev and a basic-strategy bot (needs TYPESAFE_API_KEY)
  python main.py --rounds 20 --min-bet 5 --max-bet 500
  python main.py --simulate 1000000     basic strategy alone; prints the house edge
"""

import argparse
import os
import random
from pathlib import Path

from blackjack.cards import Shoe
from blackjack.players import BasicStrategyPlayer, HumanPlayer, JevPlayer
from blackjack.rules import TableRules
from blackjack.session_log import SessionLog
from blackjack.table import Table
from blackjack.watchers import TerminalPrinter


def load_env(path: Path = Path(__file__).parent / ".env") -> None:
    """Load KEY=VALUE lines from .env into the environment (real environment variables win)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if value.strip():
                os.environ.setdefault(key.strip(), value.strip())


def play(args) -> None:
    if args.jev:
        first = JevPlayer(bet=args.bet)
        printer = TerminalPrinter()  # Jev plays on its own, so print every hand
    else:
        first = HumanPlayer("Human")
        # The human already sees their own hand and the dealer, so print only the other players.
        printer = TerminalPrinter(hide_players=(first.name,), show_dealer=False)
    rules = TableRules(min_bet=args.min_bet, max_bet=args.max_bet)
    log = SessionLog()
    watchers = [log, printer]
    table = Table(rules, Shoe(rules.num_decks, random.Random(args.seed)), watchers)
    table.sit(first, args.bankroll)
    table.sit(BasicStrategyPlayer("Basic bot", bet=args.bet), args.bankroll)
    table.play_session(args.rounds)
    print(f"Log written to {log.path}")


def simulate(args) -> None:
    """Checks the rules engine: basic strategy should lose about 0.4-0.5% of the amount bet.
    Not logged, since millions of rounds would make a huge file."""
    bet = 10  # a multiple of 2, so 3:2 payouts and surrenders are exact
    table = Table(shoe=Shoe(6, random.Random(args.seed)))
    table.sit(BasicStrategyPlayer("Basic bot", bet), bet * args.simulate * 10)
    wagered = net = 0
    for _ in range(args.simulate):
        for hand in table.play_round()["Basic bot"].hands:
            wagered += hand.bet
            net += hand.net
    print(f"{args.simulate} rounds, {wagered} wagered, net {net:+}")
    print(f"House edge: {-net / (bet * args.simulate):.3%} of initial bets")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--bankroll", type=int, default=1000)
    parser.add_argument("--min-bet", type=int, default=10)
    parser.add_argument("--max-bet", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--jev", action="store_true", help="seat Jev instead of a human and print every hand")
    parser.add_argument("--bet", type=int, default=None, help="fixed bet for Jev and the bot (default: table minimum)")
    parser.add_argument("--simulate", type=int, metavar="ROUNDS", help="simulate basic strategy for this many rounds")
    args = parser.parse_args()
    load_env()
    if args.simulate:
        simulate(args)
    else:
        play(args)


if __name__ == "__main__":
    main()
