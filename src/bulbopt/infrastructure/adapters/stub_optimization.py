from __future__ import annotations


class StubOptimizationAdapter:
    def rank_candidates(self, evaluated_candidates: list[dict]) -> list[dict]:
        if not evaluated_candidates:
            raise ValueError("No evaluated candidates available for selection")
        return sorted(evaluated_candidates, key=lambda item: item["mid_score"])

    def choose_best(self, evaluated_candidates: list[dict]) -> dict:
        return self.rank_candidates(evaluated_candidates)[0]

    def summarize_ranking(self, evaluated_candidates: list[dict]) -> dict:
        ranked_candidates = self.rank_candidates(evaluated_candidates)
        best_candidate = ranked_candidates[0]
        worst_candidate = ranked_candidates[-1]
        best_mid_score = float(best_candidate["mid_score"])
        worst_mid_score = float(worst_candidate["mid_score"])
        return {
            "best_candidate_id": best_candidate["candidate_id"],
            "ranked_count": len(ranked_candidates),
            "best_mid_score": best_mid_score,
            "worst_mid_score": worst_mid_score,
            "mid_score_spread": round(worst_mid_score - best_mid_score, 6),
        }
