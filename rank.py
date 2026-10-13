# ponytail: substring match is crude ("hair" hits "chair"); Haiku triage cleans up the false positives.
def prefilter(papers, keywords):
    kw = [k.lower() for k in keywords]
    return [p for p in papers
            if p.area != "medical" or any(k in f"{p.title} {p.abstract}".lower() for k in kw)]


def pick(papers, quota, max_papers, min_score):
    ranked = sorted((p for p in papers if p.score >= min_score), key=lambda p: -p.score)
    chosen = []
    for area, n in quota.items():
        chosen += [p for p in ranked if p.area == area][:n]
    chosen.sort(key=lambda p: -p.score)
    return chosen[:max_papers]


# Tracer-bullet stand-in until triage scoring exists (issue 03 replaces it with pick()).
def first_per_area(papers, quota):
    return [p for area, n in quota.items() for p in [q for q in papers if q.area == area][:n]]
