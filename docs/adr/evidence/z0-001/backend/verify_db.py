"""Z0-001 验证：PostgreSQL 16.14 + Redis 7.4.10 容器连通性。"""
import os
import sys

import psycopg
import redis


def verify_pg() -> None:
    dsn = os.environ.get(
        "PG_DSN",
        "postgresql://hris:devpw@127.0.0.1:54329/hris_dev",
    )
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            cur.execute("SELECT current_database(), current_user")
            db, user = cur.fetchone()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS z0_verify ("
                "id SERIAL PRIMARY KEY, note TEXT NOT NULL)"
            )
            cur.execute(
                "INSERT INTO z0_verify (note) VALUES (%s) RETURNING id",
                ("z0-001",),
            )
            new_id = cur.fetchone()[0]
            cur.execute("SELECT id, note FROM z0_verify ORDER BY id")
            rows = cur.fetchall()
            cur.execute("DROP TABLE z0_verify")
        conn.commit()
    print(f"[PG]    OK  version={version}")
    print(f"[PG]    db={db} user={user}")
    print(f"[PG]    inserted_id={new_id} rows_seen={len(rows)}")


def verify_redis() -> None:
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:63800/0")
    r = redis.Redis.from_url(url)
    pong = r.ping()
    r.set("z0:key", "z0-001", ex=10)
    val = r.get("z0:key")
    r.delete("z0:key")
    info = r.info("server")
    print(f"[REDIS] PING={pong} GET={val!r} version={info['redis_version']}")


if __name__ == "__main__":
    try:
        verify_pg()
        verify_redis()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
    print("ALL OK")
