# jev-at-the-table

Putting [Jev](https://docs.typesafe.ai/introduction.md), TypeSafe AI's System One model, at the card table.

Jev doesn't generate text. It answers typed questions (Choice, Score, Noul) about a given state and returns probabilities and a confidence value. This project uses it as a game-playing agent: our code owns the rules, deck, and bookkeeping, and Jev only makes the decisions.

## Roadmap

### 1. Blackjack

Jev plays blackjack against a simulated dealer. Each decision (hit, stand, double, split, surrender) is a single Choice question over the current hand, the dealer's up card, and the legal actions.

Blackjack has a known optimal basic strategy, so we evaluate Jev on decision quality instead of win rate:

- How often Jev's choice matches basic strategy
- Expected value lost to deviations
- Whether Jev's confidence is lower on genuinely close decisions

#### Setup

Requires Python 3.10+. The game itself has no dependencies.

```sh
pip install pytest          # to run the tests
pip install typesafe-sdk    # only needed for Jev
```

For Jev, create a `.env` file in the project root with your key from the [TypeSafe console](https://console.typesafe.ai/keys). The file is gitignored, and `main.py` loads it on startup:

```sh
TYPESAFE_API_KEY=your-key-here
```

#### Play yourself

```sh
python main.py
```

You sit at a table with a basic-strategy bot. Each round you type a bet, then choose an action by its key: `h` hit, `s` stand, `d` double, `p` split, `r` surrender. Only the actions that are legal right now are offered. After your turn, the other players' decisions and results are printed; your own hand isn't repeated. Options:

| Option | Default | Meaning |
| - | - | - |
| `--rounds N` | 10 | Number of rounds in the session |
| `--bankroll N` | 1000 | Starting chips for each player |
| `--min-bet N` / `--max-bet N` | 10 / no limit | Table limits |
| `--seed N` | random | Shuffle seed, to replay the same cards |

#### Run Jev

```sh
python main.py --jev --rounds 100
```

Jev plays next to a basic-strategy bot, with no input needed. Every decision and every result is printed to the terminal, followed by each player's totals, and the whole session is saved to the log. `--bet N` sets the fixed bet for both players (default: the table minimum), and the options above work too.

#### Stopping early

- **Type `q` at the bet prompt** to leave the table. This ends the whole session.
- **Press Ctrl+C at any time**, including during a Jev run.

Either way, the unfinished round is cancelled and every player gets back the chips they had before it. Completed rounds count as normal. The log records a `round_cancelled` line, and `session_end` says why the session stopped in `stopped_early` (`null` when it ran to the end).

#### Check the rules engine

```sh
python main.py --simulate 1000000
```

Plays basic strategy alone (no Jev, no log) and prints the house edge. It should be about 0.4%.

#### Session logs

Every session played with `main.py` writes a JSON Lines file to `blackjack/logs/` (not committed), one JSON object per line:

- `session_start`: time, rules, players and starting bankrolls
- `decision`: the full state a player saw and the action it took
- `round`: dealer cards and every player's hands, outcomes and bankrolls
- `round_cancelled`: a round that was stopped part-way and undone
- `session_end`: each player's hands, wins, losses, pushes, surrenders, net result and final bankroll, plus `stopped_early`

#### Tests

```sh
pytest
```

#### Code layout

The table owns the cards and chips; players only receive read-only views and answer with a bet or an action. Everything that crosses that boundary is defined in `blackjack/api.py`, and every player type (`HumanPlayer`, `BasicStrategyPlayer`, `JevPlayer`, and later LLMs) implements the same three methods from `blackjack/players/base.py`. The table also reports to watchers (`blackjack/watchers.py`), such as the session log and the terminal printer. Watchers only receive read-only data and players never see them, so printing or logging can't change the game or leak one player's hand to another.

### 2. Poker

Heads-up no-limit hold'em, with Jev playing against LLMs and against itself.

- Actions and bet sizes are a Choice over a discrete set (fold, check/call, half-pot, pot, all-in).
- Jev's per-option probabilities can be sampled to produce a mixed strategy, not just an argmax.
- Results are reported in bb/100 with confidence intervals, using duplicate deals to reduce variance.

## License

MIT
