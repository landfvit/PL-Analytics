import os
import requests
import psycopg
from dotenv import load_dotenv

load_dotenv()

API_key = os.getenv("API_FOOTBALL_KEY")

url = "https://v3.football.api-sports.io/fixtures"

headers = {
    "x-apisports-key": API_key
}

params = {
    "league": 39,
    "season": 2024
}

response = requests.get(
    url,
    headers=headers,
    params=params
)

data = response.json()

print("TOTAL FIXTURES:", data["results"])
print(
    "Remaining:",
    response.headers.get("x-ratelimit-requests-remaining")
)

conn = psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER")
)

with conn.cursor() as cursor:

    for match in data["response"]:

        fixture = match["fixture"]
        league = match["league"]
        teams = match["teams"]
        goals = match["goals"]

        home_team = teams["home"]
        away_team = teams["away"]

        # 1. HOME TEAM
        cursor.execute(
            """
            INSERT INTO teams (
                team_id,
                team_name
            )
            VALUES (%s, %s)
            ON CONFLICT (team_id)
            DO UPDATE SET
                team_name = EXCLUDED.team_name;
            """,
            (
                home_team["id"],
                home_team["name"]
            )
        )

        # 2. AWAY TEAM
        cursor.execute(
            """
            INSERT INTO teams (
                team_id,
                team_name
            )
            VALUES (%s, %s)
            ON CONFLICT (team_id)
            DO UPDATE SET
                team_name = EXCLUDED.team_name;
            """,
            (
                away_team["id"],
                away_team["name"]
            )
        )

        # 3. FIXTURE
        cursor.execute(
            """
            INSERT INTO fixtures (
                fixture_id,
                league_id,
                season,
                match_date,
                status,
                home_team_id,
                home_team_name,
                away_team_id,
                away_team_name,
                home_goals,
                away_goals
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (fixture_id)
            DO UPDATE SET
                match_date = EXCLUDED.match_date,
                status = EXCLUDED.status,
                home_team_id = EXCLUDED.home_team_id,
                home_team_name = EXCLUDED.home_team_name,
                away_team_id = EXCLUDED.away_team_id,
                away_team_name = EXCLUDED.away_team_name,
                home_goals = EXCLUDED.home_goals,
                away_goals = EXCLUDED.away_goals;
            """,
            (
                fixture["id"],
                league["id"],
                league["season"],
                fixture["date"],
                fixture["status"]["short"],
                home_team["id"],
                home_team["name"],
                away_team["id"],
                away_team["name"],
                goals["home"],
                goals["away"]
            )
        )

conn.commit()
conn.close()





