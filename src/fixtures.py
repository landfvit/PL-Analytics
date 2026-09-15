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

# get fixtures from api
response = requests.get(
    url,
    headers=headers,
    params=params
)

data = response.json()

print("Total fixtures:", data["results"])

print(
    "Remaining:",
    response.headers.get("x-ratelimit-requests-remaining")
)

# connect to database
conn = psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

with conn.cursor() as cursor:

    for match in data["response"]:

        fixture = match["fixture"]
        league = match["league"]
        teams = match["teams"]
        goals = match["goals"]

        home_team = teams["home"]
        away_team = teams["away"]

        # insert league
        cursor.execute(
            """
            INSERT INTO leagues (
                league_id,
                league_name,
                country_name
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (league_id)
            DO UPDATE SET
                league_name = EXCLUDED.league_name,
                country_name = EXCLUDED.country_name;
            """,
            (
                league["id"],
                league["name"],
                league["country"]
            )
        )

        # insert season
        cursor.execute(
            """
            INSERT INTO seasons (
                league_id,
                season
            )
            VALUES (%s, %s)
            ON CONFLICT (league_id, season)
            DO NOTHING;
            """,
            (
                league["id"],
                league["season"]
            )
        )

        # insert home team
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

        # insert away team
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

        # insert fixture
        cursor.execute(
            """
            INSERT INTO fixtures (
                fixture_id,
                league_id,
                season,
                match_date,
                status,
                home_team_id,
                away_team_id,
                home_goals,
                away_goals
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (fixture_id)
            DO UPDATE SET
                league_id = EXCLUDED.league_id,
                season = EXCLUDED.season,
                match_date = EXCLUDED.match_date,
                status = EXCLUDED.status,
                home_team_id = EXCLUDED.home_team_id,
                away_team_id = EXCLUDED.away_team_id,
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
                away_team["id"],
                goals["home"],
                goals["away"]
            )
        )

# save changes
conn.commit()
conn.close()

