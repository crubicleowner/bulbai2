from __future__ import annotations


class StubOptimizationAdapter:
    def choose_best(self, evaluated_candidates: list[dict]) -> dict:
        if not evaluated_candidates:
            raise ValueError("No evaluated candidates available for selection")
        return sorted(evaluated_candidates, key=lambda item: item["mid_score"])[0]
