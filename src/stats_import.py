import os
import time
import requests
import psycopg
from dotenv import load_dotenv


load_dotenv()

API_key = os.getenv("API_FOOTBALL_KEY")


def percentage_to_number(value):
    if value is None:
        return None

    return float(str(value).replace("%", ""))


# connect to database
conn = psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

# get fixtures without statistics
with conn.cursor() as cursor:
    cursor.execute(
        """
        SELECT f.fixture_id
        FROM fixtures f
        LEFT JOIN fixture_statistics s
            ON f.fixture_id = s.fixture_id
        WHERE f.status = 'FT'
          AND s.fixture_id IS NULL
        ORDER BY f.match_date
        LIMIT 20;
        """
    )

    fixtures = cursor.fetchall()

print("fixtures to import:", len(fixtures))

url = "https://v3.football.api-sports.io/fixtures/statistics"

headers = {
    "x-apisports-key": API_key
}

for row in fixtures:

    fixture_id = row[0]

    print("importing fixture:", fixture_id)

    params = {
        "fixture": fixture_id
    }

    response = requests.get(
        url,
        headers=headers,
        params=params
    )

    data = response.json()

    if data.get("errors"):
        print("api error:", data["errors"])
        continue

    with conn.cursor() as cursor:

        for team_data in data["response"]:

            team_id = team_data["team"]["id"]

            stats = {
                stat["type"]: stat["value"]
                for stat in team_data["statistics"]
            }

            cursor.execute(
                """
                INSERT INTO fixture_statistics (
                    fixture_id,
                    team_id,
                    shots_on_goal,
                    shots_off_goal,
                    total_shots,
                    blocked_shots,
                    shots_inside_box,
                    shots_outside_box,
                    fouls,
                    corner_kicks,
                    offsides,
                    ball_possession,
                    yellow_cards,
                    red_cards,
                    goalkeeper_saves,
                    total_passes,
                    passes_accurate,
                    passes_percentage
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (fixture_id, team_id)
                DO UPDATE SET
                    shots_on_goal = EXCLUDED.shots_on_goal,
                    shots_off_goal = EXCLUDED.shots_off_goal,
                    total_shots = EXCLUDED.total_shots,
                    blocked_shots = EXCLUDED.blocked_shots,
                    shots_inside_box = EXCLUDED.shots_inside_box,
                    shots_outside_box = EXCLUDED.shots_outside_box,
                    fouls = EXCLUDED.fouls,
                    corner_kicks = EXCLUDED.corner_kicks,
                    offsides = EXCLUDED.offsides,
                    ball_possession = EXCLUDED.ball_possession,
                    yellow_cards = EXCLUDED.yellow_cards,
                    red_cards = EXCLUDED.red_cards,
                    goalkeeper_saves = EXCLUDED.goalkeeper_saves,
                    total_passes = EXCLUDED.total_passes,
                    passes_accurate = EXCLUDED.passes_accurate,
                    passes_percentage = EXCLUDED.passes_percentage;
                """,
                (
                    fixture_id,
                    team_id,
                    stats.get("Shots on Goal"),
                    stats.get("Shots off Goal"),
                    stats.get("Total Shots"),
                    stats.get("Blocked Shots"),
                    stats.get("Shots insidebox"),
                    stats.get("Shots outsidebox"),
                    stats.get("Fouls"),
                    stats.get("Corner Kicks"),
                    stats.get("Offsides"),
                    percentage_to_number(stats.get("Ball Possession")),
                    stats.get("Yellow Cards"),
                    stats.get("Red Cards"),
                    stats.get("Goalkeeper Saves"),
                    stats.get("Total passes"),
                    stats.get("Passes accurate"),
                    percentage_to_number(stats.get("Passes %"))
                )
            )

    conn.commit()

    print(
        "remaining:",
        response.headers.get("x-ratelimit-requests-remaining")
    )

    time.sleep(7) # changes with api-football plan (currently free => 10 requests per minute)

conn.close()

print("stats import finished")