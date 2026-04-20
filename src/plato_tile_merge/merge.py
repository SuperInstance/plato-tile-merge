"""Tile merging with conflict resolution, 3-way merge, and merge scoring."""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class MergeStrategy(Enum):
    NEWEST = "newest"
    HIGHEST_CONFIDENCE = "highest_confidence"
    CONSENSUS = "consensus"
    UNION = "union"
    WEIGHTED = "weighted"
    LONGEST = "longest"

@dataclass
class MergeConflict:
    field_name: str
    values: list[str]
    resolution: str = "auto"
    confidence: float = 0.0

@dataclass
class MergeResult:
    merged_content: str
    source_ids: list[str]
    strategy: str
    conflicts: list[MergeConflict] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

class TileMerger:
    def __init__(self, default_strategy: str = "highest_confidence"):
        self.default_strategy = MergeStrategy(default_strategy)
        self._history: list[MergeResult] = []
        self._merge_count: int = 0

    def merge(self, tiles: list[dict], strategy: str = "") -> MergeResult:
        strat = MergeStrategy(strategy) if strategy else self.default_strategy
        if not tiles:
            return self._result("", [], strat)
        if len(tiles) == 1:
            t = tiles[0]
            return self._result(t.get("content", ""), [t.get("id", "")], strat,
                              confidence=t.get("confidence", 0.5))
        if len(tiles) == 2:
            return self._merge_two(tiles[0], tiles[1], strat)
        return self._merge_multi(tiles, strat)

    def merge_three_way(self, base: dict, ours: dict, theirs: dict) -> MergeResult:
        """3-way merge with base as common ancestor."""
        conflicts = []
        base_content = base.get("content", "")
        ours_content = ours.get("content", "")
        theirs_content = theirs.get("content", "")

        if ours_content == theirs_content:
            return self._result(ours_content,
                              [base.get("id", ""), ours.get("id", ""), theirs.get("id", "")],
                              MergeStrategy.CONSENSUS, confidence=1.0)
        if ours_content == base_content:
            return self._result(theirs_content,
                              [base.get("id", ""), ours.get("id", ""), theirs.get("id", "")],
                              MergeStrategy.NEWEST, confidence=theirs.get("confidence", 0.5))
        if theirs_content == base_content:
            return self._result(ours_content,
                              [base.get("id", ""), ours.get("id", ""), theirs.get("id", "")],
                              MergeStrategy.NEWEST, confidence=ours.get("confidence", 0.5))

        # Both changed — detect conflicts
        conflicts.append(MergeConflict(field_name="content",
                                       values=[ours_content, theirs_content],
                                       resolution="union"))
        merged = f"{ours_content}\n---\n{theirs_content}"
        avg_conf = (ours.get("confidence", 0.5) + theirs.get("confidence", 0.5)) / 2
        return self._result(merged,
                          [base.get("id", ""), ours.get("id", ""), theirs.get("id", "")],
                          MergeStrategy.UNION, conflicts=conflicts, confidence=avg_conf)

    def _merge_two(self, a: dict, b: dict, strat: MergeStrategy) -> MergeResult:
        conflicts = self._detect_conflicts([a, b])
        if strat == MergeStrategy.HIGHEST_CONFIDENCE:
            tiles = sorted([a, b], key=lambda t: t.get("confidence", 0), reverse=True)
            return self._result(tiles[0].get("content", ""),
                              [t.get("id", "") for t in [a, b]], strat,
                              conflicts=conflicts,
                              confidence=tiles[0].get("confidence", 0.5))
        elif strat == MergeStrategy.CONSENSUS:
            conf = (a.get("confidence", 0.5) + b.get("confidence", 0.5)) / 2
            merged = self._consensus_content(a.get("content", ""), b.get("content", ""))
            return self._result(merged, [a.get("id", ""), b.get("id", "")],
                              strat, conflicts=conflicts, confidence=conf)
        elif strat == MergeStrategy.WEIGHTED:
            wa = a.get("confidence", 0.5)
            wb = b.get("confidence", 0.5)
            total = wa + wb
            # Prefer higher confidence content
            if wa >= wb:
                return self._result(a.get("content", ""), [a.get("id", ""), b.get("id", "")],
                                  strat, conflicts=conflicts, confidence=wa / total)
            else:
                return self._result(b.get("content", ""), [a.get("id", ""), b.get("id", "")],
                                  strat, conflicts=conflicts, confidence=wb / total)
        elif strat == MergeStrategy.LONGEST:
            tiles = sorted([a, b], key=lambda t: len(t.get("content", "")), reverse=True)
            return self._result(tiles[0].get("content", ""),
                              [t.get("id", "") for t in [a, b]], strat,
                              conflicts=conflicts,
                              confidence=tiles[0].get("confidence", 0.5))
        else:  # NEWEST, UNION
            return self._result(a.get("content", "") + "\n" + b.get("content", ""),
                              [a.get("id", ""), b.get("id", "")],
                              strat, conflicts=conflicts)

    def _merge_multi(self, tiles: list[dict], strat: MergeStrategy) -> MergeResult:
        conflicts = self._detect_conflicts(tiles)
        if strat == MergeStrategy.CONSENSUS:
            conf = sum(t.get("confidence", 0.5) for t in tiles) / len(tiles)
            contents = [t.get("content", "") for t in tiles if t.get("content")]
            merged = self._consensus_content(*contents)
        else:
            tiles = sorted(tiles, key=lambda t: t.get("confidence", 0), reverse=True)
            merged = tiles[0].get("content", "")
            conf = tiles[0].get("confidence", 0.5)
        return self._result(merged, [t.get("id", "") for t in tiles],
                          strat, conflicts=conflicts, confidence=conf)

    def _consensus_content(self, *contents: str) -> str:
        """Merge multiple contents, deduplicating common lines."""
        if not contents:
            return ""
        if len(contents) == 1:
            return contents[0]
        seen = set()
        merged = []
        for content in contents:
            for line in content.split('\n'):
                stripped = line.strip()
                if stripped and stripped not in seen:
                    seen.add(stripped)
                    merged.append(line)
        return '\n'.join(merged)

    def _detect_conflicts(self, tiles: list[dict]) -> list[MergeConflict]:
        conflicts = []
        domains = set(t.get("domain", "") for t in tiles)
        if len(domains) > 1:
            conflicts.append(MergeConflict(field_name="domain",
                                           values=list(domains), resolution="auto"))
        return conflicts

    def _result(self, content: str, ids: list[str], strat: MergeStrategy,
                conflicts: list[MergeConflict] = None, confidence: float = 0.0,
                metadata: dict = None) -> MergeResult:
        mr = MergeResult(merged_content=content, source_ids=ids, strategy=strat.value,
                        conflicts=conflicts or [], confidence=confidence,
                        metadata=metadata or {})
        self._history.append(mr)
        self._merge_count += 1
        return mr

    def recent_merges(self, n: int = 10) -> list[MergeResult]:
        return self._history[-n:]

    def conflict_rate(self) -> float:
        if not self._history:
            return 0.0
        with_conflicts = sum(1 for m in self._history if m.conflicts)
        return with_conflicts / len(self._history)

    @property
    def stats(self) -> dict:
        strats = {}
        for m in self._history:
            strats[m.strategy] = strats.get(m.strategy, 0) + 1
        return {"merges": self._merge_count, "strategies_used": strats,
                "conflict_rate": round(self.conflict_rate(), 3)}
