from __future__ import annotations


class StubOptimizationAdapter:
    def rank_candidates(self, evaluated_candidates: list[dict]) -> list[dict]:
        if not evaluated_candidates:
            raise ValueError("No evaluated candidates available for selection")
        return sorted(
            evaluated_candidates,
            key=lambda item: (
                self._acceptability_priority(item.get("acceptability", {})),
                item["mid_score"],
            ),
        )

    def choose_best(self, evaluated_candidates: list[dict]) -> dict:
        return self.rank_candidates(evaluated_candidates)[0]

    def summarize_ranking(self, evaluated_candidates: list[dict]) -> dict:
        ranked_candidates = self.rank_candidates(evaluated_candidates)
        best_candidate = ranked_candidates[0]
        worst_candidate = ranked_candidates[-1]
        best_mid_score = float(best_candidate["mid_score"])
        worst_mid_score = float(worst_candidate["mid_score"])
        ok_count = sum(1 for item in ranked_candidates if self._acceptability_level(item.get("acceptability", {})) == "ok")
        warn_count = sum(
            1 for item in ranked_candidates if self._acceptability_level(item.get("acceptability", {})) == "warn"
        )
        reject_count = sum(
            1 for item in ranked_candidates if self._acceptability_level(item.get("acceptability", {})) == "reject"
        )
        return {
            "best_candidate_id": best_candidate["candidate_id"],
            "ranked_count": len(ranked_candidates),
            "acceptable_count": ok_count + warn_count,
            "unacceptable_count": reject_count,
            "ok_count": ok_count,
            "warn_count": warn_count,
            "reject_count": reject_count,
            "best_mid_score": best_mid_score,
            "worst_mid_score": worst_mid_score,
            "mid_score_spread": round(worst_mid_score - best_mid_score, 6),
        }

    def build_trace(self, evaluated_candidates: list[dict]) -> dict[str, list[str] | str]:
        ranked_candidates = self.rank_candidates(evaluated_candidates)
        if len(ranked_candidates) < 2:
            return {
                "summary": "Optimization trace: no comparisons",
                "rows": [],
            }

        rows: list[str] = []
        for current, following in zip(ranked_candidates, ranked_candidates[1:]):
            current_level = self._acceptability_level(current.get("acceptability", {}))
            following_level = self._acceptability_level(following.get("acceptability", {}))
            if self._acceptability_priority(current.get("acceptability", {})) != self._acceptability_priority(
                following.get("acceptability", {})
            ):
                reason = f"{current_level} beats {following_level}"
            else:
                reason = "lower mid_score"
            contributions = self._format_contribution_delta(current, following)
            rows.append(
                f"{current.get('candidate_id', 'n/a')} over {following.get('candidate_id', 'n/a')}: {reason} ({contributions})"
            )

        comparison_word = "comparison" if len(rows) == 1 else "comparisons"
        return {
            "summary": f"Optimization trace: {len(rows)} {comparison_word}",
            "rows": rows,
        }

    def _format_contribution_delta(self, current: dict, following: dict) -> str:
        current_components = current.get("score_components", {})
        following_components = following.get("score_components", {})
        return (
            f"resistance={current_components.get('resistance_proxy', 'n/a')} vs "
            f"{following_components.get('resistance_proxy', 'n/a')}, "
            f"hydro={current_components.get('hydrostatic_penalty', 'n/a')} vs "
            f"{following_components.get('hydrostatic_penalty', 'n/a')}, "
            f"calm={current_components.get('calm_water_penalty', 'n/a')} vs "
            f"{following_components.get('calm_water_penalty', 'n/a')}, "
            f"wave={current_components.get('wave_penalty', 'n/a')} vs "
            f"{following_components.get('wave_penalty', 'n/a')}, "
            f"priority={current.get('selection_priority', {}).get('selection_priority_score', 'n/a')} vs "
            f"{following.get('selection_priority', {}).get('selection_priority_score', 'n/a')}"
        )

    def _acceptability_priority(self, acceptability: dict) -> int:
        return {"ok": 0, "warn": 1, "reject": 2}.get(self._acceptability_level(acceptability), 2)

    def _acceptability_level(self, acceptability: dict) -> str:
        level = acceptability.get("level")
        if level in {"ok", "warn", "reject"}:
            return str(level)
        if acceptability.get("is_acceptable", True):
            return "ok"
        return "reject"
