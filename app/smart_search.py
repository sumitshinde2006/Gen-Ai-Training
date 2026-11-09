
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.records import load_records


def smart_search(query, top_k=5):

    records = load_records()

    if not records or not query.strip():
        return []

    documents = []

    for item in records:

        text = " ".join([
            str(item.get("variety_name") or ""),
            str(item.get("category") or ""),
            str(item.get("season") or ""),
            str(item.get("maturity_days_after_transplanting") or ""),
            str(item.get("maturity_note") or ""),
            str(item.get("yield_t_ha") or ""),
            str(item.get("storage_life") or "")
        ])

        documents.append(text)

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2)
    )

    try:

        matrix = vectorizer.fit_transform(
            documents + [query]
        )

        similarity = cosine_similarity(
            matrix[-1],
            matrix[:-1]
        ).flatten()

    except ValueError:
        return []

    ranked = similarity.argsort()[::-1]

    results = []

    for index in ranked:

        score = float(similarity[index])

        if score <= 0:
            continue

        record = records[index].copy()
        record["similarity_score"] = round(score, 4)

        results.append(record)

        if len(results) >= top_k:
            break

    return results
