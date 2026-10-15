import json
import sqlite3
from datetime import date, datetime, timedelta

DEFAULT_INTERVALS = (1, 3, 7, 21)
SCHEMA = """
create table if not exists papers(id text primary key, title text, source text, score real, sent integer);
create table if not exists runs(ts text);
create table if not exists concepts(name text primary key, taught_at text);
create table if not exists path_cache(path text, key text, payload text, primary key(path, key));
create table if not exists path_done(path text, key text, done_at text, primary key(path, key));
create table if not exists cards(id integer primary key autoincrement, path text, key text, q text, a text, created_on text, stage integer default 0, next_due text);
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

    def get_path_cache(self, path):
        return {k: json.loads(p) for k, p in self.db.execute("select key, payload from path_cache where path=?", (path,))}

    def put_path_cache(self, path, key, payload):
        self.db.execute("insert or replace into path_cache values (?,?,?)", (path, key, json.dumps(payload)))
        self.db.commit()

    def done_steps(self, path):
        return {r[0] for r in self.db.execute("select key from path_done where path=?", (path,))}

    def mark_step_done(self, path, key, when):
        self.db.execute("insert or replace into path_done values (?,?,?)", (path, key, when.isoformat()))
        self.db.commit()

    def last_step_done(self, path):
        last = self.db.execute("select max(done_at) from path_done where path=?", (path,)).fetchone()[0]
        return datetime.fromisoformat(last) if last else None

    def add_cards(self, path, key, cards, created_on, intervals=DEFAULT_INTERVALS):
        first_due = (created_on + timedelta(days=intervals[0])).isoformat()
        self.db.executemany("insert into cards(path,key,q,a,created_on,stage,next_due) values (?,?,?,?,?,0,?)",
                            [(path, key, c["q"], c["a"], created_on.isoformat(), first_due) for c in cards])
        self.db.commit()

    def due_cards(self, today, limit):
        """Cards whose next review has come, earliest first, at most `limit`. Overflow waits for tomorrow."""
        rows = self.db.execute("select id, q, a, stage from cards where next_due is not null and next_due <= ? "
                               "order by next_due, id limit ?", (today.isoformat(), limit))
        return [{"id": i, "q": q, "a": a, "stage": s} for i, q, a, s in rows]

    def mark_cards_shown(self, cards, today, intervals=DEFAULT_INTERVALS):
        """Called after delivery. The next review is scheduled from TODAY (the day it was really shown), keeping the
        gaps between the intervals, so a delay moves the whole schedule instead of costing a repetition."""
        for c in cards:
            s = c["stage"] + 1
            nxt = None if s >= len(intervals) else (today + timedelta(days=max(1, intervals[s] - intervals[s - 1]))).isoformat()
            self.db.execute("update cards set stage=?, next_due=? where id=?", (s, nxt, c["id"]))
        self.db.commit()
