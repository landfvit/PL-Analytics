import math
import os
from collections import defaultdict, deque

import numpy as np
import pandas as pd
import psycopg
from dotenv import load_dotenv

from sklearn.linear_model import (
    LogisticRegression,
    PoissonRegressor
)
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    log_loss
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


load_dotenv()

initial_elo = 1500.0
k_factor = 20.0
home_advantage = 60.0


def expected_home_score(home_elo, away_elo):
    return 1 / (
        1
        + 10 ** (
            (
                away_elo
                - (home_elo + home_advantage)
            ) / 400
        )
    )


def actual_home_score(home_goals, away_goals):
    if home_goals > away_goals:
        return 1.0

    if home_goals == away_goals:
        return 0.5

    return 0.0


def average(values):
    if not values:
        return None

    return sum(values) / len(values)


def poisson_probability(goals, expected_goals):
    return (
        math.exp(-expected_goals)
        * (expected_goals ** goals)
        / math.factorial(goals)
    )


def match_result_probabilities(
    home_expected_goals,
    away_expected_goals,
    max_goals=10
):
    home_win_probability = 0.0
    draw_probability = 0.0
    away_win_probability = 0.0

    for home_goals in range(max_goals + 1):

        home_probability = poisson_probability(
            home_goals,
            home_expected_goals
        )

        for away_goals in range(max_goals + 1):

            away_probability = poisson_probability(
                away_goals,
                away_expected_goals
            )

            score_probability = (
                home_probability
                * away_probability
            )

            if home_goals > away_goals:
                home_win_probability += (
                    score_probability
                )

            elif home_goals == away_goals:
                draw_probability += (
                    score_probability
                )

            else:
                away_win_probability += (
                    score_probability
                )

    total_probability = (
        home_win_probability
        + draw_probability
        + away_win_probability
    )

    home_win_probability /= total_probability
    draw_probability /= total_probability
    away_win_probability /= total_probability

    return [
        away_win_probability,
        draw_probability,
        home_win_probability
    ]


def evaluate_logistic(
    model,
    X_train,
    y_train,
    X_validation,
    y_validation
):
    model.fit(
        X_train,
        y_train
    )

    predictions = model.predict(
        X_validation
    )

    probabilities = model.predict_proba(
        X_validation
    )

    classes = model.named_steps[
        "model"
    ].classes_

    accuracy = accuracy_score(
        y_validation,
        predictions
    )

    loss = log_loss(
        y_validation,
        probabilities,
        labels=classes
    )

    print()
    print("LOGISTIC REGRESSION")
    print()

    print(
        "accuracy:",
        round(accuracy, 4)
    )

    print(
        "log loss:",
        round(loss, 4)
    )

    print()

    print(
        classification_report(
            y_validation,
            predictions,
            zero_division=0
        )
    )

    matrix = confusion_matrix(
        y_validation,
        predictions,
        labels=["H", "D", "A"]
    )

    print("confusion matrix:")
    print(matrix)


def evaluate_poisson(
    home_model,
    away_model,
    X_train,
    y_home_train,
    y_away_train,
    X_validation,
    y_validation,
    y_home_validation,
    y_away_validation
):
    home_model.fit(
        X_train,
        y_home_train
    )

    away_model.fit(
        X_train,
        y_away_train
    )

    home_expected_goals = home_model.predict(
        X_validation
    )

    away_expected_goals = away_model.predict(
        X_validation
    )

    probabilities = []

    for home_lambda, away_lambda in zip(
        home_expected_goals,
        away_expected_goals
    ):

        probabilities.append(
            match_result_probabilities(
                home_lambda,
                away_lambda
            )
        )

    probabilities = np.array(
        probabilities
    )

    classes = np.array(
        ["A", "D", "H"]
    )

    prediction_indexes = np.argmax(
        probabilities,
        axis=1
    )

    predictions = classes[
        prediction_indexes
    ]

    accuracy = accuracy_score(
        y_validation,
        predictions
    )

    loss = log_loss(
        y_validation,
        probabilities,
        labels=classes
    )

    print()
    print("POISSON GOAL MODEL")
    print()

    print(
        "accuracy:",
        round(accuracy, 4)
    )

    print(
        "log loss:",
        round(loss, 4)
    )

    print()

    print(
        "actual avg home goals:",
        round(
            y_home_validation.mean(),
            3
        )
    )

    print(
        "predicted avg home goals:",
        round(
            home_expected_goals.mean(),
            3
        )
    )

    print(
        "actual avg away goals:",
        round(
            y_away_validation.mean(),
            3
        )
    )

    print(
        "predicted avg away goals:",
        round(
            away_expected_goals.mean(),
            3
        )
    )

    print()

    print(
        classification_report(
            y_validation,
            predictions,
            zero_division=0
        )
    )

    matrix = confusion_matrix(
        y_validation,
        predictions,
        labels=["H", "D", "A"]
    )

    print("confusion matrix:")
    print(matrix)

    results = pd.DataFrame(
        {
            "actual":
                y_validation.values,

            "predicted":
                predictions,

            "expected_home_goals":
                home_expected_goals,

            "expected_away_goals":
                away_expected_goals,

            "prob_A":
                probabilities[:, 0],

            "prob_D":
                probabilities[:, 1],

            "prob_H":
                probabilities[:, 2]
        }
    )

    print()
    print(results.head(10))


# connect to database
conn = psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)


# load all fixtures
with conn.cursor() as cursor:

    cursor.execute(
        """
        SELECT
            fixture_id,
            match_date,
            home_team_id,
            away_team_id,
            home_goals,
            away_goals
        FROM fixtures
        WHERE status = 'FT'
        ORDER BY match_date;
        """
    )

    fixture_rows = cursor.fetchall()


fixture_columns = [
    "fixture_id",
    "match_date",
    "home_team_id",
    "away_team_id",
    "home_goals",
    "away_goals"
]

fixtures = pd.DataFrame(
    fixture_rows,
    columns=fixture_columns
)


# load ml features
with conn.cursor() as cursor:

    cursor.execute(
        """
        SELECT
            fixture_id,
            match_date,

            home_points_last_5,
            away_points_last_5,

            home_goals_scored_last_5,
            away_goals_scored_last_5,

            home_goals_conceded_last_5,
            away_goals_conceded_last_5,

            home_points_per_game,
            away_points_per_game,

            home_goal_difference,
            away_goal_difference,

            home_league_position,
            away_league_position,

            result

        FROM ml_match_features

        ORDER BY match_date;
        """
    )

    feature_rows = cursor.fetchall()


feature_columns = [
    "fixture_id",
    "match_date",

    "home_points_last_5",
    "away_points_last_5",

    "home_goals_scored_last_5",
    "away_goals_scored_last_5",

    "home_goals_conceded_last_5",
    "away_goals_conceded_last_5",

    "home_points_per_game",
    "away_points_per_game",

    "home_goal_difference",
    "away_goal_difference",

    "home_league_position",
    "away_league_position",

    "result"
]

df = pd.DataFrame(
    feature_rows,
    columns=feature_columns
)

conn.close()


# calculate elo ratings
ratings = defaultdict(
    lambda: initial_elo
)

opponent_history = defaultdict(
    lambda: deque(maxlen=5)
)

elo_rows = []


# process fixtures chronologically
for match_date, matches in fixtures.groupby(
    "match_date",
    sort=True
):

    updates = []

    for _, match in matches.iterrows():

        fixture_id = match[
            "fixture_id"
        ]

        home_team_id = match[
            "home_team_id"
        ]

        away_team_id = match[
            "away_team_id"
        ]

        home_goals = match[
            "home_goals"
        ]

        away_goals = match[
            "away_goals"
        ]

        home_elo = ratings[
            home_team_id
        ]

        away_elo = ratings[
            away_team_id
        ]

        home_opponent_elo_last_5 = average(
            opponent_history[
                home_team_id
            ]
        )

        away_opponent_elo_last_5 = average(
            opponent_history[
                away_team_id
            ]
        )

        elo_rows.append(
            {
                "fixture_id":
                    fixture_id,

                "home_elo":
                    home_elo,

                "away_elo":
                    away_elo,

                "elo_diff":
                    home_elo - away_elo,

                "home_opponent_elo_last_5":
                    home_opponent_elo_last_5,

                "away_opponent_elo_last_5":
                    away_opponent_elo_last_5
            }
        )

        expected_home = expected_home_score(
            home_elo,
            away_elo
        )

        actual_home = actual_home_score(
            home_goals,
            away_goals
        )

        home_change = (
            k_factor
            * (
                actual_home
                - expected_home
            )
        )

        away_change = -home_change

        updates.append(
            {
                "home_team_id":
                    home_team_id,

                "away_team_id":
                    away_team_id,

                "home_elo":
                    home_elo,

                "away_elo":
                    away_elo,

                "home_change":
                    home_change,

                "away_change":
                    away_change
            }
        )

    # update after same-time matches
    for update in updates:

        home_team_id = update[
            "home_team_id"
        ]

        away_team_id = update[
            "away_team_id"
        ]

        ratings[
            home_team_id
        ] += update[
            "home_change"
        ]

        ratings[
            away_team_id
        ] += update[
            "away_change"
        ]

        opponent_history[
            home_team_id
        ].append(
            update["away_elo"]
        )

        opponent_history[
            away_team_id
        ].append(
            update["home_elo"]
        )


elo_df = pd.DataFrame(
    elo_rows
)


# merge elo
df = df.merge(
    elo_df,
    on="fixture_id",
    how="left"
)


# add actual goals
df = df.merge(
    fixtures[
        [
            "fixture_id",
            "home_goals",
            "away_goals"
        ]
    ],
    on="fixture_id",
    how="left"
)


# chronological order
df = df.sort_values(
    "match_date"
).reset_index(drop=True)


# create difference features
df["points_last_5_diff"] = (
    df["home_points_last_5"]
    - df["away_points_last_5"]
)

df["goals_scored_last_5_diff"] = (
    df["home_goals_scored_last_5"]
    - df["away_goals_scored_last_5"]
)

df["goals_conceded_last_5_diff"] = (
    df["home_goals_conceded_last_5"]
    - df["away_goals_conceded_last_5"]
)

df["points_per_game_diff"] = (
    df["home_points_per_game"]
    - df["away_points_per_game"]
)

df["goal_difference_diff"] = (
    df["home_goal_difference"]
    - df["away_goal_difference"]
)

df["league_position_diff"] = (
    df["away_league_position"]
    - df["home_league_position"]
)

df["opponent_elo_last_5_diff"] = (
    df["home_opponent_elo_last_5"]
    - df["away_opponent_elo_last_5"]
)


# create absolute difference features
df["abs_points_last_5_diff"] = (
    df["points_last_5_diff"].abs()
)

df["abs_goals_scored_last_5_diff"] = (
    df[
        "goals_scored_last_5_diff"
    ].abs()
)

df["abs_goals_conceded_last_5_diff"] = (
    df[
        "goals_conceded_last_5_diff"
    ].abs()
)

df["abs_points_per_game_diff"] = (
    df[
        "points_per_game_diff"
    ].abs()
)

df["abs_goal_difference_diff"] = (
    df[
        "goal_difference_diff"
    ].abs()
)

df["abs_league_position_diff"] = (
    df[
        "league_position_diff"
    ].abs()
)

df["abs_elo_diff"] = (
    df["elo_diff"].abs()
)

df["abs_opponent_elo_last_5_diff"] = (
    df[
        "opponent_elo_last_5_diff"
    ].abs()
)


# logistic regression features
logistic_features = [
    "points_last_5_diff",
    "goals_scored_last_5_diff",
    "goals_conceded_last_5_diff",

    "points_per_game_diff",
    "goal_difference_diff",
    "league_position_diff",

    "elo_diff",
    "opponent_elo_last_5_diff",

    "abs_points_last_5_diff",
    "abs_goals_scored_last_5_diff",
    "abs_goals_conceded_last_5_diff",

    "abs_points_per_game_diff",
    "abs_goal_difference_diff",
    "abs_league_position_diff",

    "abs_elo_diff",
    "abs_opponent_elo_last_5_diff"
]


# poisson uses actual team levels
poisson_features = [
    "home_points_last_5",
    "away_points_last_5",

    "home_goals_scored_last_5",
    "away_goals_scored_last_5",

    "home_goals_conceded_last_5",
    "away_goals_conceded_last_5",

    "home_points_per_game",
    "away_points_per_game",

    "home_goal_difference",
    "away_goal_difference",

    "home_league_position",
    "away_league_position",

    "home_elo",
    "away_elo",

    "home_opponent_elo_last_5",
    "away_opponent_elo_last_5",

    "points_last_5_diff",
    "goals_scored_last_5_diff",
    "goals_conceded_last_5_diff",

    "points_per_game_diff",
    "goal_difference_diff",
    "league_position_diff",

    "elo_diff",
    "opponent_elo_last_5_diff"
]


# remove incomplete rows
required_columns = list(
    set(
        logistic_features
        + poisson_features
        + [
            "result",
            "home_goals",
            "away_goals"
        ]
    )
)

df = df.dropna(
    subset=required_columns
).reset_index(drop=True)


X_logistic = df[
    logistic_features
]

X_poisson = df[
    poisson_features
]

y = df[
    "result"
]

y_home_goals = df[
    "home_goals"
]

y_away_goals = df[
    "away_goals"
]


print(
    "rows:",
    len(df)
)


# split using complete kickoff times
unique_dates = (
    df["match_date"]
    .drop_duplicates()
    .sort_values()
    .tolist()
)

train_date_end = int(
    len(unique_dates) * 0.70
)

validation_date_end = int(
    len(unique_dates) * 0.85
)


train_dates = set(
    unique_dates[
        :train_date_end
    ]
)

validation_dates = set(
    unique_dates[
        train_date_end:
        validation_date_end
    ]
)

test_dates = set(
    unique_dates[
        validation_date_end:
    ]
)


train_mask = df[
    "match_date"
].isin(
    train_dates
)

validation_mask = df[
    "match_date"
].isin(
    validation_dates
)

test_mask = df[
    "match_date"
].isin(
    test_dates
)


X_logistic_train = X_logistic[
    train_mask
]

X_logistic_validation = X_logistic[
    validation_mask
]


X_poisson_train = X_poisson[
    train_mask
]

X_poisson_validation = X_poisson[
    validation_mask
]


y_train = y[
    train_mask
]

y_validation = y[
    validation_mask
]

y_test = y[
    test_mask
]


y_home_train = y_home_goals[
    train_mask
]

y_away_train = y_away_goals[
    train_mask
]


y_home_validation = y_home_goals[
    validation_mask
]

y_away_validation = y_away_goals[
    validation_mask
]


print(
    "training matches:",
    train_mask.sum()
)

print(
    "validation matches:",
    validation_mask.sum()
)

print(
    "test matches:",
    test_mask.sum()
)


print()

print(
    "training period:",
    df.loc[
        train_mask,
        "match_date"
    ].min(),
    "-",
    df.loc[
        train_mask,
        "match_date"
    ].max()
)

print(
    "validation period:",
    df.loc[
        validation_mask,
        "match_date"
    ].min(),
    "-",
    df.loc[
        validation_mask,
        "match_date"
    ].max()
)

print(
    "test period:",
    df.loc[
        test_mask,
        "match_date"
    ].min(),
    "-",
    df.loc[
        test_mask,
        "match_date"
    ].max()
)


# naive baseline
most_common_class = y_train.mode()[0]

baseline_predictions = [
    most_common_class
    for _ in range(
        len(y_validation)
    )
]

baseline_accuracy = accuracy_score(
    y_validation,
    baseline_predictions
)

print()

print(
    "validation naive baseline:",
    round(
        baseline_accuracy,
        4
    )
)


# logistic regression model
logistic_model = Pipeline(
    [
        (
            "scaler",
            StandardScaler()
        ),
        (
            "model",
            LogisticRegression(
                max_iter=1000
            )
        )
    ]
)


# home goals poisson model
home_poisson_model = Pipeline(
    [
        (
            "scaler",
            StandardScaler()
        ),
        (
            "model",
            PoissonRegressor(
                alpha=0.1,
                max_iter=1000
            )
        )
    ]
)


# away goals poisson model
away_poisson_model = Pipeline(
    [
        (
            "scaler",
            StandardScaler()
        ),
        (
            "model",
            PoissonRegressor(
                alpha=0.1,
                max_iter=1000
            )
        )
    ]
)


# evaluate logistic regression
evaluate_logistic(
    logistic_model,
    X_logistic_train,
    y_train,
    X_logistic_validation,
    y_validation
)


# evaluate poisson goal model
evaluate_poisson(
    home_poisson_model,
    away_poisson_model,

    X_poisson_train,

    y_home_train,
    y_away_train,

    X_poisson_validation,

    y_validation,

    y_home_validation,
    y_away_validation
)


print()
print("TEST SET")
print()

print(
    "test set is still untouched"
)

print(
    "we will use it after model selection"
)