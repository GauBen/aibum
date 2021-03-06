import shutil
import sqlite3
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from typing import List, Set, Tuple

import requests

CACHE_DIR = "cache"
DB_DIR = "db"
COVERT_ART_URL = "https://coverartarchive.org/release-group/{mbid}/front-500"


def get_cache() -> Set[str]:
    """Get all downloaded covers."""
    if not Path(CACHE_DIR).is_dir():
        Path(CACHE_DIR).mkdir()
        return set()
    return {jpg.stem for jpg in Path(CACHE_DIR).glob("*.jpg")}


def get_db() -> sqlite3.Connection:
    """Open a connection to the local database."""
    return sqlite3.connect(Path("mbdump", "mb.sqlite"))


def download_cover(mbid):
    """Download a cover."""
    try:
        url = COVERT_ART_URL.replace("{mbid}", mbid)
        r = requests.get(url, stream=True)
        if r.status_code != 200:
            return False
        with open(Path(CACHE_DIR, mbid).with_suffix(".jpg"), "wb") as f:
            for chunk in r:
                f.write(chunk)
        return True
    except KeyboardInterrupt:
        raise RuntimeError()


def download_covers(limit: List[int], genres: List[str]):
    """Download covers of selected genres."""
    start = time.time()
    cache = get_cache()
    db = get_db()
    sql = f"""
        WITH tags AS (SELECT id FROM tag WHERE name IN ({",".join(["?"] * len(genres))}))
        SELECT r.gid, t.name
        FROM release_group_tag AS rt
        INNER JOIN
            (SELECT release_group, MAX(count) AS count
            FROM release_group_tag
            WHERE tag IN tags
            GROUP BY release_group) AS agg
            ON agg.release_group = rt.release_group AND agg.count = rt.count
        INNER JOIN release_group AS r ON rt.release_group = r.id
        INNER JOIN tag AS t ON rt.tag = t.id
        WHERE rt.tag IN tags
        LIMIT {",".join(["?"] * len(limit))}
    """
    count = 0
    failed = 0
    rows: List[Tuple[str, str]] = [
        (mbid, genre)
        for (mbid, genre) in db.execute(sql, genres + list(map(str, limit)))
        if mbid not in cache
    ]
    pool = Pool()
    try:
        for ((mbid, genre), successful) in zip(
            rows, pool.imap(download_cover, map(lambda x: x[0], rows))
        ):
            count += 1
            if successful:
                print(f"[{count}] {mbid} Cover art downloaded #{genre}")
            else:
                failed += 1
                print(f"[{count}] {mbid} Download failed ({failed} fails so far)")
    except KeyboardInterrupt:
        pool.terminate()
        pool.close()

    print(f"Downloaded {count - failed} covers in {time.time() - start} seconds")


def group_covers(n: int, groups: List[List[str]]):
    """Group downloaded covers of the same genre."""
    start = time.time()
    if Path(DB_DIR).is_dir():
        shutil.rmtree(Path(DB_DIR))
    for group in groups:
        Path(DB_DIR, group[0]).mkdir(parents=True)
    genre_dic = {genre: genres[0] for genres in groups for genre in genres}
    counter = {genres[0]: 0 for genres in groups}
    db = get_db()
    cache = get_cache()
    sql = """
        SELECT t.name
        FROM tag AS t
        JOIN release_group_tag AS rt ON rt.tag = t.id
        JOIN release_group AS r ON r.id = rt.release_group
        WHERE r.gid = ?
        ORDER BY rt.count DESC
    """
    remaining = len(groups) * n
    for mbid in cache:
        if remaining <= 0:
            break
        for (genre,) in db.execute(sql, [mbid]):
            if genre not in genre_dic:
                continue
            genre = genre_dic[genre]
            if counter[genre] >= n:
                break
            remaining -= 1
            counter[genre] += 1
            shutil.copy(
                Path(CACHE_DIR, mbid).with_suffix(".jpg"),
                Path(DB_DIR, genre, mbid).with_suffix(".jpg"),
            )
            break
    for genre in counter:
        print(f" - {genre}: {counter[genre]}")
    s = sum(counter[genre] for genre in counter)
    print(f"Groupped {s} covers in {time.time() - start} seconds")


def count_covers(groups: List[List[str]]):
    """Count downloaded covers of the same genre."""
    start = time.time()
    if Path(DB_DIR).is_dir():
        shutil.rmtree(Path(DB_DIR))
    for group in groups:
        Path(DB_DIR, group[0]).mkdir(parents=True)
    genre_dic = {genre: genres[0] for genres in groups for genre in genres}
    counter = {genres[0]: 0 for genres in groups}
    db = get_db()
    cache = get_cache()
    sql = """
        SELECT t.name
        FROM tag AS t
        JOIN release_group_tag AS rt ON rt.tag = t.id
        JOIN release_group AS r ON r.id = rt.release_group
        WHERE r.gid = ?
        ORDER BY rt.count DESC
    """
    for mbid in cache:
        for (genre,) in db.execute(sql, [mbid]):
            if genre not in genre_dic:
                continue
            genre = genre_dic[genre]
            counter[genre] += 1
            break
    for genre in counter:
        print(f" - {genre}: {counter[genre]}")
    s = sum(counter[genre] for genre in counter)
    print(f"Counted {s} covers in {time.time() - start} seconds")


if __name__ == "__main__":

    def input_arg(n):
        """Try to find parameter in argv or defaults to stdin."""
        if len(sys.argv) >= n + 2:
            arg = sys.argv[n + 1]
            print(arg)
        else:
            arg = input()
        return arg

    print("== aibum ==")
    print()

    if not Path("mbdump", "mb.sqlite").is_file():
        print("[x] mbdump/mb.sqlite not found")
        sys.exit(1)

    print("a. Download and cache covers")
    print("b. Group cached covers")
    print("c. Count cached covers")
    print("d. Quit")
    print("> ", end="")
    sub_command = input_arg(0)

    if sub_command == "a":
        print("Number of covers to download")
        print("> ", end="")
        limit = list(map(int, input_arg(1).split(",")))
        print("Comma-separated genre list to download")
        print("> ", end="")
        genres = list(map(lambda s: s.strip(), input_arg(2).split(",")))
        download_covers(limit, genres)

    elif sub_command == "b":
        print("Number of covers per group")
        print("> ", end="")
        n = int(input_arg(1))
        print(
            "Comma-separated genre groups (first is used as group name / enter to start)"
        )
        i = 2
        groups = []
        while True:
            print(f"Group #{i - 1}> ", end="")
            group = input_arg(i)
            if len(group) == 0:
                break
            groups.append(group.split(","))
            i += 1
        group_covers(n, groups)

    elif sub_command == "c":
        print(
            "Comma-separated genre groups (first is used as group name / enter to start)"
        )
        i = 2
        groups = []
        while True:
            print(f"Group #{i - 1}> ", end="")
            group = input_arg(i)
            if len(group) == 0:
                break
            groups.append(group.split(","))
            i += 1
        count_covers(groups)
