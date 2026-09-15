CREATE OR REPLACE VIEW ml_match_features AS

WITH team_matches AS (

    SELECT
        fixture_id,
        match_date,
        home_team_id AS team_id,

        CASE
            WHEN home_goals > away_goals THEN 3
            WHEN home_goals = away_goals THEN 1
            ELSE 0
        END AS points

    FROM fixtures
    WHERE status = 'FT'

    UNION ALL

    SELECT
        fixture_id,
        match_date,
        away_team_id AS team_id,

        CASE
            WHEN away_goals > home_goals THEN 3
            WHEN away_goals = home_goals THEN 1
            ELSE 0
        END AS points

    FROM fixtures
    WHERE status = 'FT'
),

team_form AS (

    SELECT
        fixture_id,
        team_id,
        match_date,

        SUM(points) OVER (
            PARTITION BY team_id
            ORDER BY match_date
            ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
        ) AS points_last_5,

        COUNT(*) OVER (
            PARTITION BY team_id
            ORDER BY match_date
            ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
        ) AS matches_last_5

    FROM team_matches
)

SELECT
    f.fixture_id,
    f.match_date,

    f.home_team_id,
    f.away_team_id,

    home.team_name AS home_team,
    away.team_name AS away_team,

    home_form.points_last_5 AS home_points_last_5,
    away_form.points_last_5 AS away_points_last_5,

    CASE
        WHEN f.home_goals > f.away_goals THEN 'H'
        WHEN f.home_goals = f.away_goals THEN 'D'
        ELSE 'A'
    END AS result

FROM fixtures f

JOIN teams home
    ON f.home_team_id = home.team_id

JOIN teams away
    ON f.away_team_id = away.team_id

JOIN team_form home_form
    ON f.fixture_id = home_form.fixture_id
    AND f.home_team_id = home_form.team_id

JOIN team_form away_form
    ON f.fixture_id = away_form.fixture_id
    AND f.away_team_id = away_form.team_id

WHERE f.status = 'FT'
  AND home_form.matches_last_5 = 5
  AND away_form.matches_last_5 = 5;