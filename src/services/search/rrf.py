from collections import defaultdict
def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    k: int = 60,
) -> list[tuple[str, float]]:
    scores = defaultdict(float)
    for ranked_list in ranked_lists:
        for idx, doc_id, in enumerate(ranked_list):
            scores[doc_id] += 1/(k+idx+1)




    return sorted(scores.items(), key=lambda x: x[1], reverse=True)