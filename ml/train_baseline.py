import os
from collections import defaultdict, deque

import pandas as pd
import psycopg
from dotenv import load_dotenv

from sklearn.linear_model import LogisticRegression
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


# process matches with same kickoff together
for match_date, matches in fixtures.groupby(
    "match_date",
    sort=True
):

    updates = []

    for _, match in matches.iterrows():

        fixture_id = match["fixture_id"]

        home_team_id = match["home_team_id"]
        away_team_id = match["away_team_id"]

        home_goals = match["home_goals"]
        away_goals = match["away_goals"]

        home_elo = ratings[home_team_id]
        away_elo = ratings[away_team_id]

        home_opponent_elo_last_5 = average(
            opponent_history[home_team_id]
        )

        away_opponent_elo_last_5 = average(
            opponent_history[away_team_id]
        )

        elo_rows.append(
            {
                "fixture_id": fixture_id,
                "home_elo": home_elo,
                "away_elo": away_elo,
                "elo_diff": home_elo - away_elo,
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
            * (actual_home - expected_home)
        )

        away_change = -home_change

        updates.append(
            {
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_elo": home_elo,
                "away_elo": away_elo,
                "home_change": home_change,
                "away_change": away_change
            }
        )

    # update ratings after same-time matches
    for update in updates:

        home_team_id = update["home_team_id"]
        away_team_id = update["away_team_id"]

        ratings[home_team_id] += update["home_change"]
        ratings[away_team_id] += update["away_change"]

        opponent_history[home_team_id].append(
            update["away_elo"]
        )

        opponent_history[away_team_id].append(
            update["home_elo"]
        )


elo_df = pd.DataFrame(elo_rows)


# merge elo features
df = df.merge(
    elo_df,
    on="fixture_id",
    how="left"
)


# create signed difference features
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
    df["goals_scored_last_5_diff"].abs()
)

df["abs_goals_conceded_last_5_diff"] = (
    df["goals_conceded_last_5_diff"].abs()
)

df["abs_points_per_game_diff"] = (
    df["points_per_game_diff"].abs()
)

df["abs_goal_difference_diff"] = (
    df["goal_difference_diff"].abs()
)

df["abs_league_position_diff"] = (
    df["league_position_diff"].abs()
)

df["abs_elo_diff"] = (
    df["elo_diff"].abs()
)

df["abs_opponent_elo_last_5_diff"] = (
    df["opponent_elo_last_5_diff"].abs()
)


# select features
feature_names = [
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


# remove incomplete rows
df = df.dropna(
    subset=feature_names + ["result"]
).reset_index(drop=True)


X = df[feature_names]

y = df["result"]


print("rows:", len(df))


# time based split
split_index = int(
    len(df) * 0.8
)

X_train = X.iloc[:split_index]
X_test = X.iloc[split_index:]

y_train = y.iloc[:split_index]
y_test = y.iloc[split_index:]


print(
    "training matches:",
    len(X_train)
)

print(
    "test matches:",
    len(X_test)
)


# train model
model = Pipeline(
    [
        (
            "scaler",
            StandardScaler()
        ),
        (
            "logistic",
            LogisticRegression(
                max_iter=1000
            )
        )
    ]
)

model.fit(
    X_train,
    y_train
)


# predictions
predictions = model.predict(
    X_test
)

probabilities = model.predict_proba(
    X_test
)

classes = model.named_steps[
    "logistic"
].classes_


# accuracy
accuracy = accuracy_score(
    y_test,
    predictions
)

print()
print(
    "accuracy:",
    round(accuracy, 4)
)


# log loss
loss = log_loss(
    y_test,
    probabilities,
    labels=classes
)

print(
    "log loss:",
    round(loss, 4)
)


# naive baseline
most_common_class = y_train.mode()[0]

baseline_predictions = [
    most_common_class
    for _ in range(len(y_test))
]

baseline_accuracy = accuracy_score(
    y_test,
    baseline_predictions
)

print(
    "naive baseline accuracy:",
    round(baseline_accuracy, 4)
)


# class order
print()
print(
    "class order:",
    classes
)


# classification report
print()
print(
    classification_report(
        y_test,
        predictions,
        zero_division=0
    )
)


# confusion matrix
matrix = confusion_matrix(
    y_test,
    predictions,
    labels=["H", "D", "A"]
)

print(
    "confusion matrix:"
)

print(matrix)


# prediction probabilities
results = pd.DataFrame(
    {
        "actual": y_test.values,
        "predicted": predictions
    }
)

for index, class_name in enumerate(
    classes
):

    results[
        f"prob_{class_name}"
    ] = probabilities[:, index]


print()
print(
    results.head(10)
)


# show features
print()
print("features:")

for feature in feature_names:
    print(feature)