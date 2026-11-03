"""Feature names, labels and groups. Ported verbatim from the notebook (cells 9, 11, 20, 22, 35, 39).

The tooltips (plain-language descriptions) are new and used by the website.
"""
from __future__ import annotations

POS_NAME = {"D": "Defender", "M": "Midfielder", "F": "Forward"}

# notebook cell 11: per90_src  (feature -> how it is built from Kaggle columns; see features.py)
PER90_FEATURES = [
    "goals_p90", "np_goals_p90", "assists_p90", "xg_p90", "xa_p90",
    "shots_p90", "shots_on_target_p90", "key_passes_p90", "big_chances_created_p90",
    "dribbles_p90", "was_fouled_p90", "tackles_p90", "tackles_won_p90", "interceptions_p90",
    "clearances_p90", "ball_recovery_p90", "aerial_won_p90", "dispossessed_p90", "touches_p90",
    "yellow_p90", "red_p90",
]
NUM_FEATURES = PER90_FEATURES + ["pass_accuracy", "start_share", "minutes", "age", "age_sq", "team_strength"]
CAT_FEATURES = ["position", "nation_group"]

# notebook cell 35
SIM_FEATURES = [
    "goals_p90", "np_goals_p90", "assists_p90", "xg_p90", "xa_p90", "shots_p90", "shots_on_target_p90",
    "key_passes_p90", "big_chances_created_p90", "dribbles_p90", "was_fouled_p90",
    "tackles_won_p90", "interceptions_p90", "clearances_p90", "ball_recovery_p90", "aerial_won_p90",
    "dispossessed_p90", "touches_p90", "pass_accuracy",
]

# notebook cell 39
RADAR = ["xg_p90", "xa_p90", "key_passes_p90", "dribbles_p90", "tackles_won_p90", "interceptions_p90", "aerial_won_p90", "pass_accuracy"]
RADAR_LABELS = ["xG/90", "xA/90", "Key passes/90", "Dribbles/90", "Tackles won/90", "Interceptions/90", "Aerial duels won/90", "Pass accuracy"]

# Kaggle columns the pipeline reads (notebook cells 5, 9, 11)
KAGGLE_COLUMNS = [
    "player_name", "team_name", "position", "minutesPlayed", "goals", "penaltyGoals", "assists",
    "expectedGoals", "expectedAssists", "totalShots", "shotsOnTarget", "keyPasses", "bigChancesCreated",
    "successfulDribbles", "wasFouled", "tackles", "tacklesWon", "interceptions", "clearances", "ballRecovery",
    "aerialDuelsWon", "dispossessed", "touches", "yellowCards", "redCards", "accuratePassesPercentage",
    "matchesStarted", "appearances", "rating",
]

# notebook cell 7
TEAM_MAP = {
    "Manchester Utd": "Manchester United", "Newcastle": "Newcastle United", "Nottingham": "Nottingham Forest",
    "Tottenham": "Tottenham Hotspur", "West Ham": "West Ham United", "Wolves": "Wolverhampton",
    "Brighton": "Brighton & Hove Albion",
}

# notebook cell 20
PRETTY = {
    "goals_p90": "Goals /90", "np_goals_p90": "Non-penalty goals /90", "assists_p90": "Assists /90", "xg_p90": "xG /90", "xa_p90": "xA /90",
    "shots_p90": "Shots /90", "shots_on_target_p90": "Shots on target /90", "key_passes_p90": "Key passes /90",
    "big_chances_created_p90": "Big chances created /90", "dribbles_p90": "Successful dribbles /90", "was_fouled_p90": "Times fouled /90",
    "tackles_p90": "Tackles /90", "tackles_won_p90": "Tackles won /90", "interceptions_p90": "Interceptions /90",
    "clearances_p90": "Clearances /90", "ball_recovery_p90": "Ball recoveries /90", "aerial_won_p90": "Aerial duels won /90",
    "dispossessed_p90": "Dispossessed /90", "touches_p90": "Touches /90", "yellow_p90": "Yellow cards /90", "red_p90": "Red cards /90",
    "pass_accuracy": "Pass accuracy %", "start_share": "Share of matches started", "minutes": "Minutes played",
    "age": "Age", "age_sq": "Age squared", "team_strength": "Team strength",
}

# notebook cell 22
GROUPS = {
    "Attacking output": ["goals_p90", "np_goals_p90", "xg_p90", "shots_p90", "shots_on_target_p90"],
    "Creativity & ball use": ["assists_p90", "xa_p90", "key_passes_p90", "big_chances_created_p90", "dribbles_p90", "was_fouled_p90", "touches_p90", "dispossessed_p90"],
    "Defending": ["tackles_p90", "tackles_won_p90", "interceptions_p90", "clearances_p90", "ball_recovery_p90", "aerial_won_p90"],
    "Discipline": ["yellow_p90", "red_p90"],
    "Passing": ["pass_accuracy"],
    "Playing time": ["minutes", "start_share"],
    "Age": ["age", "age_sq"],
    "Team context": ["team_strength"],
}
PERF_GROUPS = ["Attacking output", "Creativity & ball use", "Defending", "Discipline", "Passing"]
FEATURE_TO_GROUP = {f: g for g, fs in GROUPS.items() for f in fs}


def pretty(n: str) -> str:
    if n in PRETTY:
        return PRETTY[n]
    if n == "position":
        return "Position"
    if n == "nation_group":
        return "Nationality"
    if n.startswith("position_"):
        return "Position: " + POS_NAME.get(n.split("_", 1)[1], n.split("_", 1)[1])
    if n.startswith("nation_group_"):
        return "Nationality: " + n[len("nation_group_"):]
    return n


def group_of(n: str) -> str:
    if n in FEATURE_TO_GROUP:
        return FEATURE_TO_GROUP[n]
    if n == "position" or n.startswith("position_"):
        return "Position"
    if n == "nation_group" or n.startswith("nation_group_"):
        return "Nationality"
    return "Other"


def feat_of(n: str) -> str:
    """notebook cell 42: merge age+age_sq and one-hot columns into one 'feature'."""
    if n in ("age", "age_sq"):
        return "age"
    if n.startswith("position_"):
        return "position"
    if n.startswith("nation_group_"):
        return "nation_group"
    return n


# Plain-language tooltips (new, for the website)
TOOLTIPS = {
    "goals_p90": "Goals scored per 90 minutes played.",
    "np_goals_p90": "Goals per 90 minutes, not counting penalties.",
    "assists_p90": "Assists (the last pass before a goal) per 90 minutes.",
    "xg_p90": "Expected goals per 90: how many goals an average finisher would score from this player's chances.",
    "xa_p90": "Expected assists per 90: how many assists this player's passes would produce with average finishing by teammates.",
    "shots_p90": "Shots per 90 minutes.",
    "shots_on_target_p90": "Shots that would have gone in without the goalkeeper, per 90 minutes.",
    "key_passes_p90": "Passes that lead directly to a shot, per 90 minutes.",
    "big_chances_created_p90": "Passes that create a clear scoring chance, per 90 minutes.",
    "dribbles_p90": "Times the player beat an opponent with the ball, per 90 minutes.",
    "was_fouled_p90": "Times the player was fouled, per 90 minutes.",
    "tackles_p90": "Tackles attempted per 90 minutes.",
    "tackles_won_p90": "Tackles that won the ball, per 90 minutes.",
    "interceptions_p90": "Opponent passes cut out, per 90 minutes.",
    "clearances_p90": "Times the player cleared the ball away from danger, per 90 minutes.",
    "ball_recovery_p90": "Loose balls won back, per 90 minutes.",
    "aerial_won_p90": "Headers and aerial challenges won, per 90 minutes.",
    "dispossessed_p90": "Times the player lost the ball to a tackle, per 90 minutes (lower is better).",
    "touches_p90": "Times the player touched the ball, per 90 minutes. A sign of involvement.",
    "yellow_p90": "Yellow cards per 90 minutes.",
    "red_p90": "Red cards per 90 minutes.",
    "pass_accuracy": "Share of the player's passes that reached a teammate.",
    "start_share": "Share of the player's appearances in which he started the match.",
    "minutes": "Total league minutes played this season.",
    "age": "Age in years (from FBref). The model also uses age squared so that value can rise and then fall with age.",
    "age_sq": "Age multiplied by itself. Lets the model learn that value peaks at a certain age.",
    "team_strength": "How strong the player's club is: the minutes-weighted average match rating of its players.",
    "position": "Defender, midfielder or forward (goalkeepers are excluded).",
    "nation_group": "Nationality, grouped into the six most common nations in the sample plus 'other'.",
}
