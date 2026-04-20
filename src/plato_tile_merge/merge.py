"""Tile merging with conflict resolution."""
import time
from dataclasses import dataclass, field
from enum import Enum

class MergeStrategy(Enum):
    NEWEST = "newest"
    HIGHEST_CONFIDENCE = "highest_confidence"
    CONSENSUS = "consensus"
    UNION = "union"

@dataclass
class MergeResult:
    merged_content: str
    source_ids: list[str]
    strategy: str
    conflicts: list[str] = field(default_factory=list)
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)

class TileMerger:
    def __init__(self, default_strategy: str = "highest_confidence"):
        self.default_strategy = MergeStrategy(default_strategy)
        self._history: list[MergeResult] = []

    def merge(self, tiles: list[dict], strategy: str = "") -> MergeResult:
        strat = MergeStrategy(strategy) if strategy else self.default_strategy
        if not tiles:
            return MergeResult(merged_content="", source_ids=[], strategy=strat.value)
        if len(tiles) == 1:
            t = tiles[0]
            return MergeResult(merged_content=t.get("content", ""), source_ids=[t.get("id", "")],
                              strategy=strat.value, confidence=t.get("confidence", 0.5))
        conflicts = self._detect_conflicts(tiles)
        if strat == MergeStrategy.HIGHEST_CONFIDENCE:
            tiles.sort(key=lambda t: t.get("confidence", 0), reverse=True)
            result = tiles[0]
        elif strat == MergeStrategy.CONSENSUS:
            conf = sum(t.get("confidence", 0.5) for t in tiles) / len(tiles)
            contents = [t.get("content", "") for t in tiles if t.get("content")]
            mr = MergeResult(merged_content=" | ".join(contents), source_ids=[t.get("id", "") for t in tiles],
                           strategy=strat.value, conflicts=conflicts, confidence=conf)
            self._history.append(mr)
            return mr
        else:
            result = tiles[0]
        mr = MergeResult(merged_content=result.get("content", ""),
                        source_ids=[t.get("id", "") for t in tiles],
                        strategy=strat.value, conflicts=conflicts,
                        confidence=result.get("confidence", 0.5))
        self._history.append(mr)
        return mr

    def _detect_conflicts(self, tiles: list[dict]) -> list[str]:
        domains = set(t.get("domain", "") for t in tiles)
        return [f"Domain conflict: {domains}"] if len(domains) > 1 else []

    @property
    def stats(self) -> dict:
        return {"merges": len(self._history),
                "strategies_used": list(set(m.strategy for m in self._history))}
