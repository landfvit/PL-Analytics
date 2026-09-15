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
                status = EXCLUDED.status,
                home_goals = EXCLUDED.home_goals,
                away_goals = EXCLUDED.away_goals;
            """,
            (
                fixture["id"],
                league["id"],
                league["season"],
                fixture["date"],
                fixture["status"]["short"],
                teams["home"]["id"],
                teams["home"]["name"],
                teams["away"]["id"],
                teams["away"]["name"],
                goals["home"],
                goals["away"]
            )
        )

conn.commit()
conn.close()


