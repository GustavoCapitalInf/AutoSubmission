"""Count gate firings without reducing repeated observations to presence flags."""
from collections import Counter


def summarize_occurrences(occurrences) -> dict:
    from vlm.gate import REASONS

    grouped = {}
    for event in occurrences:
        code, page = event['code'], event['page']
        if code not in REASONS or (page is not None and (type(page) is not int or page < 1)):
            raise ValueError('gate_occurrence_invalid')
        grouped.setdefault(code, Counter())[page] += 1
    return {code: {'count': sum(counts.values()),
                   'pages': [{'page': page, 'count': counts[page]}
                             for page in sorted(p for p in counts if p is not None)],
                   'document_count': counts[None]}
            for code, counts in sorted(grouped.items())}
