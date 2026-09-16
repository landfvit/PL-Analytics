from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.database import fetch_all, fetch_one


BASE_DIR = Path(__file__).resolve().parent.parent

WEB_DIR = BASE_DIR / "web"
TEMPLATES_DIR = WEB_DIR / "templates"
PUBLIC_STATIC_DIR = WEB_DIR / "static"


app = FastAPI(
    title="Premier League Analytics API",
    version="0.1.0"
)


# legacy static files for the developer dashboard
app.mount(
    "/static",
    StaticFiles(directory=WEB_DIR),
    name="static"
)


# public website assets
app.mount(
    "/assets",
    StaticFiles(directory=PUBLIC_STATIC_DIR),
    name="assets"
)


templates = Jinja2Templates(
    directory=TEMPLATES_DIR
)


@app.get(
    "/",
    response_class=HTMLResponse,
    include_in_schema=False
)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "sport": "football",
            "active_page": "scores"
        }
    )


@app.get(
    "/matches/{fixture_id}",
    response_class=HTMLResponse,
    include_in_schema=False
)
def match_page(
    request: Request,
    fixture_id: int
):
    return templates.TemplateResponse(
        request=request,
        name="match.html",
        context={
            "sport": "football",
            "active_page": "scores",
            "fixture_id": fixture_id
        }
    )


@app.get(
    "/admin",
    include_in_schema=False
)
def admin_dashboard():
    return FileResponse(
        WEB_DIR / "admin.html"
    )


@app.get("/api/health")
def health():
    return {
        "name": "Premier League Analytics API",
        "status": "running"
    }


@app.get("/api/data/seasons")
def get_season_data():
    rows = fetch_all(
        """
        SELECT
            league_id,
            league_name,
            season,
            teams,
            total_fixtures,
            finished_fixtures,
            fixtures_with_complete_stats,
            fixtures_with_partial_stats,
            fixtures_without_stats,
            statistics_coverage_percentage,
            first_match_date,
            last_match_date
        FROM season_data_summary
        ORDER BY season;
        """
    )

    return {
        "count": len(rows),
        "seasons": rows
    }


@app.get("/api/data/imports")
def get_imports(
    limit: int = Query(
        default=20,
        ge=1,
        le=100
    )
):
    rows = fetch_all(
        """
        SELECT
            import_run_id,
            import_type,
            league_id,
            season,
            started_at,
            finished_at,
            status,
            rows_received,
            rows_inserted,
            api_requests,
            error_message
        FROM import_runs
        ORDER BY started_at DESC
        LIMIT %s;
        """,
        (
            limit,
        )
    )

    return {
        "count": len(rows),
        "imports": rows
    }


@app.get("/api/data/quality")
def get_data_quality():
    checks = []

    row = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM fixtures f

        LEFT JOIN teams home
            ON f.home_team_id = home.team_id

        LEFT JOIN teams away
            ON f.away_team_id = away.team_id

        WHERE home.team_id IS NULL
           OR away.team_id IS NULL;
        """
    )

    checks.append(
        {
            "name": "fixtures_without_valid_teams",
            "issues": row["count"]
        }
    )

    row = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM fixtures
        WHERE status = 'FT'
          AND (
              home_goals IS NULL
              OR away_goals IS NULL
          );
        """
    )

    checks.append(
        {
            "name": "finished_fixtures_without_goals",
            "issues": row["count"]
        }
    )

    row = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM fixture_data_status
        WHERE data_status = 'partial';
        """
    )

    checks.append(
        {
            "name": "fixtures_with_partial_statistics",
            "issues": row["count"]
        }
    )

    row = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM fixture_statistics
        WHERE ball_possession < 0
           OR ball_possession > 100;
        """
    )

    checks.append(
        {
            "name": "invalid_possession_values",
            "issues": row["count"]
        }
    )

    row = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM fixture_statistics
        WHERE passes_percentage < 0
           OR passes_percentage > 100;
        """
    )

    checks.append(
        {
            "name": "invalid_pass_percentage_values",
            "issues": row["count"]
        }
    )

    row = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM fixture_statistics
        WHERE shots_on_goal < 0
           OR shots_off_goal < 0
           OR total_shots < 0
           OR blocked_shots < 0
           OR fouls < 0
           OR corner_kicks < 0
           OR offsides < 0
           OR yellow_cards < 0
           OR red_cards < 0
           OR goalkeeper_saves < 0
           OR total_passes < 0
           OR passes_accurate < 0;
        """
    )

    checks.append(
        {
            "name": "negative_statistics_values",
            "issues": row["count"]
        }
    )

    row = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM fixture_statistics
        WHERE passes_accurate > total_passes;
        """
    )

    checks.append(
        {
            "name": "accurate_passes_greater_than_total",
            "issues": row["count"]
        }
    )

    row = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM fixture_statistics
        WHERE shots_on_goal > total_shots;
        """
    )

    checks.append(
        {
            "name": "shots_on_goal_greater_than_total",
            "issues": row["count"]
        }
    )

    row = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM import_runs
        WHERE status = 'running';
        """
    )

    checks.append(
        {
            "name": "unfinished_import_runs",
            "issues": row["count"]
        }
    )

    total_issues = sum(
        check["issues"]
        for check in checks
    )

    return {
        "status": (
            "ok"
            if total_issues == 0
            else "issues_found"
        ),
        "total_issues": total_issues,
        "checks": checks
    }


@app.get("/api/teams")
def get_teams():
    rows = fetch_all(
        """
        SELECT
            t.team_id,
            t.team_name,

            COUNT(
                DISTINCT f.fixture_id
            ) AS fixtures

        FROM teams t

        LEFT JOIN fixtures f
            ON t.team_id = f.home_team_id
            OR t.team_id = f.away_team_id

        GROUP BY
            t.team_id,
            t.team_name

        ORDER BY t.team_name;
        """
    )

    return {
        "count": len(rows),
        "teams": rows
    }


@app.get("/api/fixtures/{fixture_id}")
def get_fixture_detail(
    fixture_id: int
):
    fixture = fetch_one(
        """
        SELECT
            f.fixture_id,
            f.league_id,
            f.season,
            f.match_date,
            f.status,

            f.home_team_id,
            home.team_name AS home_team,

            f.away_team_id,
            away.team_name AS away_team,

            f.home_goals,
            f.away_goals

        FROM fixtures f

        JOIN teams home
            ON f.home_team_id = home.team_id

        JOIN teams away
            ON f.away_team_id = away.team_id

        WHERE f.fixture_id = %s;
        """,
        (
            fixture_id,
        )
    )

    if fixture is None:
        raise HTTPException(
            status_code=404,
            detail="Fixture not found"
        )

    statistics = fetch_all(
        """
        SELECT
            s.team_id,
            t.team_name,

            s.shots_on_goal,
            s.shots_off_goal,
            s.total_shots,
            s.blocked_shots,

            s.shots_inside_box,
            s.shots_outside_box,

            s.fouls,
            s.corner_kicks,
            s.offsides,

            s.ball_possession,

            s.yellow_cards,
            s.red_cards,

            s.goalkeeper_saves,

            s.total_passes,
            s.passes_accurate,
            s.passes_percentage

        FROM fixture_statistics s

        JOIN teams t
            ON s.team_id = t.team_id

        WHERE s.fixture_id = %s

        ORDER BY
            CASE
                WHEN s.team_id = %s
                THEN 0
                ELSE 1
            END;
        """,
        (
            fixture_id,
            fixture["home_team_id"]
        )
    )

    return {
        "fixture": fixture,
        "statistics": statistics,
        "statistics_count": len(statistics)
    }


@app.get("/api/fixtures")
def get_fixtures(
    season: int | None = None,
    status: str | None = None,
    data_status: str | None = None,
    team: str | None = None,
    limit: int = Query(
        default=30,
        ge=1,
        le=500
    )
):
    query = """
        SELECT
            fixture_id,
            league_id,
            season,
            match_date,
            home_team,
            away_team,
            status,
            home_goals,
            away_goals,
            statistics_rows,
            data_status

        FROM fixture_data_status

        WHERE 1 = 1
    """

    params = []

    if season is not None:
        query += """
            AND season = %s
        """

        params.append(
            season
        )

    if status is not None:
        query += """
            AND status = %s
        """

        params.append(
            status
        )

    if data_status is not None:
        query += """
            AND data_status = %s
        """

        params.append(
            data_status
        )

    if team is not None:
        query += """
            AND (
                home_team = %s
                OR away_team = %s
            )
        """

        params.append(
            team
        )

        params.append(
            team
        )

    query += """
        ORDER BY match_date DESC
        LIMIT %s;
    """

    params.append(
        limit
    )

    rows = fetch_all(
        query,
        tuple(params)
    )

    return {
        "count": len(rows),
        "fixtures": rows
    }