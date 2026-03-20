import aiosqlite
import json
import logging
import os
from typing import Optional

logger = logging.getLogger('DebateBot')

DB_PATH = os.getenv("DB_PATH", "debate_rounds.db")


async def init_db():
    """Create tables if they don't exist. Called once at bot startup."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rounds (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL DEFAULT (datetime('now')),
                format_type     TEXT NOT NULL,
                round_type      TEXT NOT NULL,
                motion          TEXT,
                infoslide       TEXT,
                winner          TEXT,
                bp_rankings     TEXT,
                chair_id        INTEGER NOT NULL,
                chair_username  TEXT NOT NULL,
                gov_total       INTEGER,
                opp_total       INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                discord_id      INTEGER PRIMARY KEY,
                username        TEXT NOT NULL,
                elo             REAL DEFAULT 1000.0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS speaker_scores (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id        INTEGER NOT NULL REFERENCES rounds(id),
                participant_id  INTEGER NOT NULL REFERENCES participants(discord_id),
                username        TEXT NOT NULL,
                team_key        TEXT NOT NULL,
                position_name   TEXT NOT NULL,
                score           INTEGER NOT NULL,
                is_reply        INTEGER NOT NULL DEFAULT 0,
                UNIQUE(round_id, participant_id, is_reply)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS judge_ratings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id        INTEGER NOT NULL REFERENCES rounds(id),
                judge_id        INTEGER NOT NULL REFERENCES participants(discord_id),
                debater_id      INTEGER NOT NULL REFERENCES participants(discord_id),
                debater_username TEXT NOT NULL,
                score           INTEGER NOT NULL,
                feedback        TEXT,
                UNIQUE(round_id, judge_id, debater_id)
            )
        """)
        await db.commit()
        logger.info(f"Database initialized at {DB_PATH}")


async def _upsert_participant(db, discord_id: int, username: str):
    """Insert or update a participant's username (preserves elo)."""
    await db.execute(
        """INSERT INTO participants (discord_id, username)
           VALUES (?, ?)
           ON CONFLICT(discord_id) DO UPDATE SET username = excluded.username""",
        (discord_id, username)
    )


async def log_round(debate_round) -> int:
    """Log a completed round to the database. Returns the DB round ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        is_bp = debate_round.bp_ballot is not None
        ballot = debate_round.bp_ballot if is_bp else debate_round.ballot

        # Determine format and round type strings
        format_label = (debate_round.format_label or "").upper()
        format_map = {"1V1": "1v1", "AP": "ap", "BP": "bp"}
        format_type = format_map.get(format_label, format_label.lower())
        round_type = debate_round.round_type.value if hasattr(debate_round.round_type, 'value') else str(debate_round.round_type)

        # Chair judge info
        chair = ballot.judge
        chair_id = chair.id
        chair_username = chair.name

        if is_bp:
            winner = None
            bp_rankings = json.dumps(debate_round.bp_ballot.rankings)
            gov_total = None
            opp_total = None
        else:
            winner = debate_round.ballot.winner
            bp_rankings = None
            gov_total = debate_round.ballot.gov_total
            opp_total = debate_round.ballot.opp_total

        # Insert round
        cursor = await db.execute(
            """INSERT INTO rounds (format_type, round_type, motion, infoslide, winner,
                                   bp_rankings, chair_id, chair_username, gov_total, opp_total)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (format_type, round_type, debate_round.motion, debate_round.infoslide,
             winner, bp_rankings, chair_id, chair_username, gov_total, opp_total)
        )
        db_round_id = cursor.lastrowid

        # Upsert all participants
        # Judge(s)
        all_judges = debate_round.judges.get_all_judges()
        for judge in all_judges:
            await _upsert_participant(db, judge.id, judge.name)

        # Debaters + speaker scores
        if is_bp:
            bp_ballot = debate_round.bp_ballot
            for team_key in ("og", "oo", "cg", "co"):
                scores = bp_ballot.team_scores.get(team_key, [])
                for ss in scores:
                    await _upsert_participant(db, ss.member.id, ss.member.name)
                    await db.execute(
                        """INSERT INTO speaker_scores
                           (round_id, participant_id, username, team_key, position_name, score, is_reply)
                           VALUES (?, ?, ?, ?, ?, ?, 0)""",
                        (db_round_id, ss.member.id, ss.member.name, team_key, ss.position_name, ss.score)
                    )
        else:
            ap_ballot = debate_round.ballot
            # Gov substantive scores
            for ss in ap_ballot.gov_scores:
                await _upsert_participant(db, ss.member.id, ss.member.name)
                await db.execute(
                    """INSERT INTO speaker_scores
                       (round_id, participant_id, username, team_key, position_name, score, is_reply)
                       VALUES (?, ?, ?, ?, ?, ?, 0)""",
                    (db_round_id, ss.member.id, ss.member.name, "gov", ss.position_name, ss.score)
                )
            # Opp substantive scores
            for ss in ap_ballot.opp_scores:
                await _upsert_participant(db, ss.member.id, ss.member.name)
                await db.execute(
                    """INSERT INTO speaker_scores
                       (round_id, participant_id, username, team_key, position_name, score, is_reply)
                       VALUES (?, ?, ?, ?, ?, ?, 0)""",
                    (db_round_id, ss.member.id, ss.member.name, "opp", ss.position_name, ss.score)
                )
            # Gov reply
            if ap_ballot.gov_reply:
                rr = ap_ballot.gov_reply
                await db.execute(
                    """INSERT INTO speaker_scores
                       (round_id, participant_id, username, team_key, position_name, score, is_reply)
                       VALUES (?, ?, ?, ?, ?, ?, 1)""",
                    (db_round_id, rr.member.id, rr.member.name, "gov", rr.position_name, rr.score)
                )
            # Opp reply
            if ap_ballot.opp_reply:
                rr = ap_ballot.opp_reply
                await db.execute(
                    """INSERT INTO speaker_scores
                       (round_id, participant_id, username, team_key, position_name, score, is_reply)
                       VALUES (?, ?, ?, ?, ?, ?, 1)""",
                    (db_round_id, rr.member.id, rr.member.name, "opp", rr.position_name, rr.score)
                )

        await db.commit()
        logger.info(f"Logged round {debate_round.round_id} to database as DB round {db_round_id}")
        return db_round_id


async def log_judge_ratings(db_round_id: int, debate_round):
    """Insert judge rating records after all debaters have rated."""
    async with aiosqlite.connect(DB_PATH) as db:
        judge = debate_round.bp_ballot.judge if debate_round.bp_ballot else debate_round.ballot.judge

        for rating in debate_round.judge_ratings:
            await _upsert_participant(db, rating.debater.id, rating.debater.name)
            await db.execute(
                """INSERT OR IGNORE INTO judge_ratings
                   (round_id, judge_id, debater_id, debater_username, score, feedback)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (db_round_id, judge.id, rating.debater.id, rating.debater.name,
                 rating.score, rating.feedback)
            )

        await db.commit()
        logger.info(f"Logged judge ratings for DB round {db_round_id}")


async def get_debater_stats(discord_id: int) -> Optional[dict]:
    """Get stats for a participant as a debater."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Check participant exists
        cursor = await db.execute(
            "SELECT username FROM participants WHERE discord_id = ?", (discord_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None

        # Total rounds and avg substantive score
        cursor = await db.execute(
            """SELECT COUNT(DISTINCT round_id) as rounds, AVG(score) as avg_score
               FROM speaker_scores WHERE participant_id = ? AND is_reply = 0""",
            (discord_id,)
        )
        row = await cursor.fetchone()
        total_rounds = row["rounds"] or 0
        avg_score = round(row["avg_score"], 1) if row["avg_score"] else None

        if total_rounds == 0:
            return None

        # Win/loss (1v1/AP — where winner is not null)
        cursor = await db.execute(
            """SELECT
                SUM(CASE WHEN
                    (ss.team_key IN ('gov') AND r.winner = 'Government') OR
                    (ss.team_key IN ('opp') AND r.winner = 'Opposition')
                    THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN
                    (ss.team_key IN ('gov') AND r.winner = 'Opposition') OR
                    (ss.team_key IN ('opp') AND r.winner = 'Government')
                    THEN 1 ELSE 0 END) as losses
               FROM speaker_scores ss
               JOIN rounds r ON r.id = ss.round_id
               WHERE ss.participant_id = ? AND ss.is_reply = 0 AND r.winner IS NOT NULL""",
            (discord_id,)
        )
        row = await cursor.fetchone()
        wins = row["wins"] or 0
        losses = row["losses"] or 0

        # BP placements
        cursor = await db.execute(
            """SELECT r.bp_rankings, ss.team_key
               FROM speaker_scores ss
               JOIN rounds r ON r.id = ss.round_id
               WHERE ss.participant_id = ? AND r.bp_rankings IS NOT NULL AND ss.is_reply = 0""",
            (discord_id,)
        )
        bp_rows = await cursor.fetchall()
        bp_rounds = 0
        bp_rank_sum = 0
        bp_placement_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        for bp_row in bp_rows:
            rankings = json.loads(bp_row["bp_rankings"])
            team_key = bp_row["team_key"]
            rank = rankings.get(team_key)
            if rank:
                bp_rounds += 1
                bp_rank_sum += rank
                bp_placement_counts[rank] = bp_placement_counts.get(rank, 0) + 1
        avg_bp_rank = round(bp_rank_sum / bp_rounds, 1) if bp_rounds > 0 else None

        # Positions played
        cursor = await db.execute(
            """SELECT position_name, COUNT(*) as count
               FROM speaker_scores WHERE participant_id = ? AND is_reply = 0
               GROUP BY position_name ORDER BY count DESC""",
            (discord_id,)
        )
        positions = {row["position_name"]: row["count"] for row in await cursor.fetchall()}

        # Formats played
        cursor = await db.execute(
            """SELECT r.format_type, COUNT(DISTINCT r.id) as count
               FROM rounds r JOIN speaker_scores ss ON r.id = ss.round_id
               WHERE ss.participant_id = ? AND ss.is_reply = 0
               GROUP BY r.format_type""",
            (discord_id,)
        )
        formats = {row["format_type"]: row["count"] for row in await cursor.fetchall()}

        return {
            "total_rounds": total_rounds,
            "wins": wins,
            "losses": losses,
            "avg_score": avg_score,
            "avg_bp_rank": avg_bp_rank,
            "bp_rounds": bp_rounds,
            "bp_placements": bp_placement_counts if bp_rounds > 0 else None,
            "positions": positions,
            "formats": formats,
        }


async def get_judge_stats(discord_id: int) -> Optional[dict]:
    """Get stats for a participant as a judge."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Rounds judged
        cursor = await db.execute(
            """SELECT COUNT(*) as rounds FROM rounds WHERE chair_id = ?""",
            (discord_id,)
        )
        row = await cursor.fetchone()
        rounds_judged = row["rounds"] or 0

        if rounds_judged == 0:
            return None

        # Average rating and feedback
        cursor = await db.execute(
            """SELECT AVG(score) as avg_rating, COUNT(*) as total_ratings
               FROM judge_ratings WHERE judge_id = ?""",
            (discord_id,)
        )
        row = await cursor.fetchone()
        avg_rating = round(row["avg_rating"], 1) if row["avg_rating"] else None
        total_ratings = row["total_ratings"] or 0

        # Recent feedback (last 10)
        cursor = await db.execute(
            """SELECT debater_username, score, feedback
               FROM judge_ratings WHERE judge_id = ? AND feedback IS NOT NULL
               ORDER BY id DESC LIMIT 10""",
            (discord_id,)
        )
        feedback_list = [
            {"from": row["debater_username"], "score": row["score"], "feedback": row["feedback"]}
            for row in await cursor.fetchall()
        ]

        # Formats judged
        cursor = await db.execute(
            """SELECT format_type, COUNT(*) as count
               FROM rounds WHERE chair_id = ? GROUP BY format_type""",
            (discord_id,)
        )
        formats = {row["format_type"]: row["count"] for row in await cursor.fetchall()}

        return {
            "rounds_judged": rounds_judged,
            "avg_rating": avg_rating,
            "total_ratings": total_ratings,
            "feedback": feedback_list,
            "formats": formats,
        }


async def get_participant_stats(discord_id: int) -> Optional[dict]:
    """Get combined debater + judge stats for a participant."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT username FROM participants WHERE discord_id = ?", (discord_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        username = row["username"]

    debater = await get_debater_stats(discord_id)
    judge = await get_judge_stats(discord_id)

    if not debater and not judge:
        return None

    return {
        "username": username,
        "debater": debater,
        "judge": judge,
    }
