"""Fetch new papers from free sources. fetch_* hit the network; parse_* are pure."""
from dataclasses import dataclass


@dataclass
class Paper:
    id: str
    title: str
    abstract: str
    source: str
    area: str  # "finance" | "science" | "medical"
    journal: str
    url: str
    published: str  # YYYY-MM-DD
    kind: str  # "peer" | "preprint"
    fulltext_url: str = ""
    score: float = 0.0
