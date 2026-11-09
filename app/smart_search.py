
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.records import load_records


def smart_search(query, top_k=5):
    """Return the most relevant agricultural records for a query."""

    if not query or not query.strip():
        return []

    records = load_records()

    if not records:
        return []

    documents = []

    for item in records:
        searchable_text = " ".join(
            str(item.get(field) or "")
            for field in [
                "variety_name",
                "category",
                "season",
                "maturity_days_after_transplanting",
                "maturity_note",
                "yield_t_ha",
                "storage_life",
            ]
        )

        documents.append(searchable_text)

    try:
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2)
        )

        matrix = vectorizer.fit_transform(documents + [query])

        scores = cosine_similarity(
            matrix[-1],
            matrix[:-1]
        ).flatten()

    except ValueError:
        return []

    ranked_indices = scores.argsort()[::-1]

    results = []

    for index in ranked_indices:
        score = float(scores[index])

        # Do not return unrelated records.
        if score <= 0:
            continue

        result = records[index].copy()
        result["similarity_score"] = round(score, 4)

        results.append(result)

        if len(results) >= top_k:
            break

    return results
