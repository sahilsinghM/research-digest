import sqlite3
from datetime import datetime, timedelta

SCHEMA = """
create table if not exists papers(id text primary key, title text, source text, score real, sent integer);
create table if not exists runs(ts text);
"""


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def since(self, lookback_days, now):
        last = self.db.execute("select max(ts) from runs").fetchone()[0]
        return datetime.fromisoformat(last) if last else now - timedelta(days=lookback_days)

    def record_success(self, ts):
        self.db.execute("insert into runs values (?)", (ts.isoformat(),))
        self.db.commit()

    def mark_sent(self, p):
        self.db.execute("insert or replace into papers values (?,?,?,?,1)", (p.id, p.title, p.source, p.score))
        self.db.commit()

    # ponytail: the same paper under two ids (arXiv id vs later journal DOI) is not merged.
    def new_only(self, papers):
        sent = {r[0] for r in self.db.execute("select id from papers where sent=1")}
        return [p for p in papers if p.id not in sent]
