const matchPage = document.getElementById(
    "match-page"
);

const fixtureId = matchPage.dataset.fixtureId;

const matchDate = document.getElementById(
    "match-date"
);

const matchStatus = document.getElementById(
    "match-status"
);

const homeTeam = document.getElementById(
    "home-team"
);

const awayTeam = document.getElementById(
    "away-team"
);

const homeScore = document.getElementById(
    "home-score"
);

const awayScore = document.getElementById(
    "away-score"
);

const statisticsContainer = document.getElementById(
    "statistics-container"
);


async function fetchJSON(url) {
    const response = await fetch(
        url
    );

    if (!response.ok) {
        throw new Error(
            `request failed: ${response.status}`
        );
    }

    return response.json();
}


function formatDate(value) {
    const date = new Date(
        value
    );

    return new Intl.DateTimeFormat(
        "en-GB",
        {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        }
    ).format(
        date
    );
}


function displayValue(value, suffix = "") {
    if (
        value === null
        || value === undefined
    ) {
        return "-";
    }

    return `${value}${suffix}`;
}


function createStatRow(
    name,
    homeValue,
    awayValue,
    suffix = ""
) {
    const row = document.createElement(
        "div"
    );

    row.className =
        "stat-row";

    row.innerHTML = `
        <div class="stat-value home">
            ${displayValue(
                homeValue,
                suffix
            )}
        </div>

        <div class="stat-name">
            ${name}
        </div>

        <div class="stat-value away">
            ${displayValue(
                awayValue,
                suffix
            )}
        </div>
    `;

    return row;
}


function renderStatistics(
    statistics
) {
    statisticsContainer.innerHTML = "";

    if (statistics.length < 2) {
        statisticsContainer.innerHTML = `
            <div class="no-statistics">
                Detailed statistics are not available for this match.
            </div>
        `;

        return;
    }

    const home = statistics[0];
    const away = statistics[1];

    const rows = [
        [
            "Ball possession",
            home.ball_possession,
            away.ball_possession,
            "%"
        ],
        [
            "Total shots",
            home.total_shots,
            away.total_shots
        ],
        [
            "Shots on goal",
            home.shots_on_goal,
            away.shots_on_goal
        ],
        [
            "Shots off goal",
            home.shots_off_goal,
            away.shots_off_goal
        ],
        [
            "Blocked shots",
            home.blocked_shots,
            away.blocked_shots
        ],
        [
            "Shots inside box",
            home.shots_inside_box,
            away.shots_inside_box
        ],
        [
            "Shots outside box",
            home.shots_outside_box,
            away.shots_outside_box
        ],
        [
            "Corner kicks",
            home.corner_kicks,
            away.corner_kicks
        ],
        [
            "Fouls",
            home.fouls,
            away.fouls
        ],
        [
            "Offsides",
            home.offsides,
            away.offsides
        ],
        [
            "Yellow cards",
            home.yellow_cards,
            away.yellow_cards
        ],
        [
            "Red cards",
            home.red_cards,
            away.red_cards
        ],
        [
            "Goalkeeper saves",
            home.goalkeeper_saves,
            away.goalkeeper_saves
        ],
        [
            "Total passes",
            home.total_passes,
            away.total_passes
        ],
        [
            "Accurate passes",
            home.passes_accurate,
            away.passes_accurate
        ],
        [
            "Pass accuracy",
            home.passes_percentage,
            away.passes_percentage,
            "%"
        ]
    ];

    for (const row of rows) {
        statisticsContainer.appendChild(
            createStatRow(
                row[0],
                row[1],
                row[2],
                row[3] || ""
            )
        );
    }
}


function renderFixture(data) {
    const fixture = data.fixture;

    homeTeam.textContent =
        fixture.home_team;

    awayTeam.textContent =
        fixture.away_team;

    homeScore.textContent =
        fixture.home_goals ?? "-";

    awayScore.textContent =
        fixture.away_goals ?? "-";

    matchStatus.textContent =
        fixture.status;

    matchDate.textContent =
        formatDate(
            fixture.match_date
        );

    renderStatistics(
        data.statistics
    );
}


async function loadMatch() {
    try {
        const data = await fetchJSON(
            `/api/fixtures/${fixtureId}`
        );

        renderFixture(
            data
        );

    } catch (error) {
        console.error(
            error
        );

        statisticsContainer.innerHTML = `
            <div class="no-statistics">
                Could not load match data.
            </div>
        `;
    }
}


loadMatch();