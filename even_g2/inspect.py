"""Local read-only recovery inventory. Never changes outcomes or replays work."""
import sqlite3


def inventory(directory):
    path = directory / 'intents.sqlite3'
    if not path.exists():
        return {'sessions': 0, 'turns': 0, 'unresolved': []}
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON')
        rows = db.execute("""SELECT turns.id AS turn_id, turns.session AS session_id,
            sessions.device, sessions.backend_id AS hermes_session_id,
            turns.run AS run_id, turns.status, turns.created
            FROM turns JOIN sessions ON sessions.id=turns.session
            WHERE turns.status NOT IN ('completed','failed','cancelled','interrupted','rejected')
            ORDER BY turns.created""").fetchall()
        return {'sessions': db.execute('SELECT count(*) FROM sessions').fetchone()[0],
                'turns': db.execute('SELECT count(*) FROM turns').fetchone()[0],
                'unresolved': [dict(row) for row in rows]}
    finally:
        db.close()
