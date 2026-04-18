from __future__ import annotations


class StubEvaluationAdapter:
    def evaluate_candidates(self, candidates: list[dict]) -> list[dict]:
        evaluated: list[dict] = []
        for index, candidate in enumerate(candidates, start=1):
            evaluated.append(
                {
                    **candidate,
                    "status": "mid_score_ready",
                    "fast_score": 1.0 / index,
                    "mid_score": 10.0 - index,
                }
            )
        return evaluated
