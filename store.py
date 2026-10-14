import sqlite3
from datetime import datetime, timedelta

SCHEMA = """
create table if not exists papers(id text primary key, title text, source text, score real, sent integer);
create table if not exists runs(ts text);
create table if not exists concepts(name text primary key, taught_at text);
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

    def record_scores(self, papers):
        """Remember triage scores so an unsent paper is not scored again tomorrow. Never touches the sent flag."""
        self.db.executemany(
            "insert into papers(id,title,source,score,sent) values (?,?,?,?,0) "
            "on conflict(id) do update set score=excluded.score",
            [(p.id, p.title, p.source, p.score) for p in papers])
        self.db.commit()

    def cached_scores(self, papers):
        ids = [p.id for p in papers]
        out = {}
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            q = f"select id, score from papers where score is not null and id in ({','.join('?' * len(chunk))})"
            out.update(self.db.execute(q, chunk).fetchall())
        return out

    def record_concept(self, name, when):
        self.db.execute("insert into concepts values (?,?) on conflict(name) do update set taught_at=excluded.taught_at",
                        (name, when.isoformat()))
        self.db.commit()

    def recent_concepts(self, limit=40):
        return [r[0] for r in self.db.execute("select name from concepts order by taught_at desc limit ?", (limit,))]
