"""Session logs: one JSON Lines file per session (one JSON object per line).

Each file has a session_start line, a decision line for every player decision,
a round line for every round, and a session_end line with each player's totals.
"""

import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from blackjack.api import Action, DecisionView, Outcome, RoundResult
from blackjack.cards import Card
from blackjack.rules import TableRules
from blackjack.watchers import SeatInfo, TableWatcher

LOG_DIR = Path(__file__).parent / "logs"


class SessionLog(TableWatcher):
    def __init__(self, path: str | Path | None = None):
        if path is None:
            LOG_DIR.mkdir(exist_ok=True)
            path = LOG_DIR / f"session-{datetime.now():%Y%m%d-%H%M%S-%f}.jsonl"
        self.path = Path(path)
        self._file = open(self.path, "w", encoding="utf-8", buffering=1)  # flushed line by line
        self._stats: dict[str, dict] = {}
        self._rounds = 0

    def start(self, rules: TableRules, seats: tuple[SeatInfo, ...]) -> None:
        self._stats = {
            seat.name: {
                "type": seat.player_type,
                "start_bankroll": seat.bankroll,
                "hands": 0,
                "wins": 0,
                "losses": 0,
                "pushes": 0,
                "surrenders": 0,
                "net": 0,
            }
            for seat in seats
        }
        self._write(
            {
                "event": "session_start",
                "time": datetime.now().isoformat(timespec="seconds"),
                "rules": _jsonable(rules),
                "players": [_jsonable(seat) for seat in seats],
            }
        )

    def decision(self, round_no: int, player_name: str, view: DecisionView, action: Action) -> None:
        self._write(
            {"event": "decision", "round": round_no, "player": player_name, "state": _jsonable(view), "action": action.value}
        )

    def round_end(
        self, round_no: int, dealer_cards: tuple[Card, ...], dealer_total: int, results: Mapping[str, RoundResult]
    ) -> None:
        self._rounds += 1
        for name, result in results.items():
            stats = self._stats[name]
            for hand in result.hands:
                stats["hands"] += 1
                stats["net"] += hand.net
                if hand.outcome in (Outcome.WIN, Outcome.BLACKJACK):
                    stats["wins"] += 1
                elif hand.outcome is Outcome.LOSE:
                    stats["losses"] += 1
                elif hand.outcome is Outcome.PUSH:
                    stats["pushes"] += 1
                else:
                    stats["surrenders"] += 1
        self._write(
            {
                "event": "round",
                "round": round_no,
                "dealer_cards": _jsonable(dealer_cards),
                "dealer_total": dealer_total,
                "players": {name: _jsonable(result) for name, result in results.items()},
            }
        )

    def round_cancelled(self, round_no: int) -> None:
        self._write({"event": "round_cancelled", "round": round_no})

    def end(self, final_bankrolls: Mapping[str, int], stop_reason: str | None = None) -> None:
        players = {name: {**stats, "final_bankroll": final_bankrolls[name]} for name, stats in self._stats.items()}
        self._write(
            {
                "event": "session_end",
                "time": datetime.now().isoformat(timespec="seconds"),
                "rounds": self._rounds,
                "stopped_early": stop_reason,
                "players": players,
            }
        )
        self._file.close()

    def _write(self, record: dict) -> None:
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _jsonable(value):
    """Turn cards, enums, dataclasses and tuples into plain JSON values."""
    if isinstance(value, Card):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {f.name: _jsonable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
