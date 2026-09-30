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

### 2. Poker

Heads-up no-limit hold'em, with Jev playing against LLMs and against itself.

- Actions and bet sizes are a Choice over a discrete set (fold, check/call, half-pot, pot, all-in).
- Jev's per-option probabilities can be sampled to produce a mixed strategy, not just an argmax.
- Results are reported in bb/100 with confidence intervals, using duplicate deals to reduce variance.

## License

MIT
