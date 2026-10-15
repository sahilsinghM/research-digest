import json
import sqlite3
from datetime import date, datetime, timedelta

SCHEMA = """
create table if not exists papers(id text primary key, title text, source text, score real, sent integer);
create table if not exists runs(ts text);
create table if not exists concepts(name text primary key, taught_at text);
create table if not exists path_cache(path text, key text, payload text, primary key(path, key));
create table if not exists path_done(path text, key text, done_at text, primary key(path, key));
create table if not exists cards(id integer primary key autoincrement, path text, key text, q text, a text, created_on text);
create table if not exists card_showings(card_id integer, interval integer, shown_on text, primary key(card_id, interval));
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

    def add_cards(self, path, key, cards, created_on):
        self.db.executemany("insert into cards(path,key,q,a,created_on) values (?,?,?,?,?)",
                            [(path, key, c["q"], c["a"], created_on.isoformat()) for c in cards])
        self.db.commit()

    def due_cards(self, today, intervals, limit):
        """Cards whose 1/3/7/21-day (configurable) moment has come and that were not shown for it yet, earliest due
        first, at most `limit`. A missed day catches up; overflow waits for tomorrow; nothing is lost."""
        shown = set(self.db.execute("select card_id, interval from card_showings"))
        due = []
        for cid, q, a, created in self.db.execute("select id, q, a, created_on from cards order by id"):
            made = date.fromisoformat(created)
            age = (today - made).days
            ready = [i for i in sorted(intervals) if i <= age and (cid, i) not in shown]
            if ready:
                due.append((made + timedelta(days=ready[0]), cid, {"id": cid, "q": q, "a": a, "intervals": ready}))
        return [c for _, _, c in sorted(due, key=lambda x: (x[0], x[1]))[:limit]]

    def mark_cards_shown(self, cards, today):
        """Called after delivery. Every overdue interval counts as shown, so a catch-up is not replayed."""
        self.db.executemany("insert or ignore into card_showings values (?,?,?)",
                            [(c["id"], i, today.isoformat()) for c in cards for i in c["intervals"]])
        self.db.commit()
