"""Glossary (intent 7) and how-to guides (intent 8). Static explanatory text, no player data."""
from __future__ import annotations

GLOSSARY = {
    "per 90": ("Per 90 minutes",
               "A per-90 number divides a count by minutes played and multiplies by 90, so players with different playing time "
               "can be compared. Example: 8 goals in 2,700 minutes is 8 ÷ 30 = 0.27 goals per 90."),
    "xg": ("xG (expected goals)",
           "xG measures the quality of a player's chances: how many goals an average finisher would score from the same shots. "
           "A shot from a penalty spot is worth more xG than a shot from 30 metres."),
    "xa": ("xA (expected assists)",
           "xA measures the quality of the chances a player creates with passes: how many assists those passes would produce "
           "if teammates finished like an average player."),
    "shap": ("SHAP value",
             "SHAP splits one estimate into contributions from each feature. The model starts at a base value (the average player) "
             "and each feature pushes the estimate up or down. It shows what the model uses, not what causes value."),
    "waterfall": ("Waterfall chart",
                  "A waterfall chart shows one player's SHAP breakdown: it starts at the base value and adds each feature's push "
                  "(green up, red down) until it reaches the final estimate."),
    "base value": ("Base value",
                   "The model's average prediction across all players. Every individual explanation starts from this number."),
    "cosine similarity": ("Cosine similarity",
                          "A score from 0 to 1 that compares the shape of two players' statistical profiles. Each statistic is first "
                          "compared with the player's own position (a z-score). 1 means an identical profile shape."),
    "z score": ("z-score",
                "How far a value is from the average, measured in standard deviations. Here it is computed within each position, "
                "so 2 tackles per 90 is high for a forward but normal for a defender."),
    "value filter": ("Value filter (maximum price)",
                     "In scouting, candidates are kept only if their out-of-fold estimate is at most a chosen percentage of the "
                     "target's estimate (default 60%)."),
    "out of fold": ("Out-of-fold estimate",
                    "An estimate for a player made by a model that never saw that player during training (5-fold cross-validation). "
                    "It is fairer than an in-sample estimate, so scouting uses it to compare prices."),
    "team strength": ("Team-strength indicator",
                      "How strong a player's club is: the average match rating of the club's players, weighted by minutes played."),
    "cross validation": ("Cross-validation",
                         "The training players are split into 5 parts; the model is trained on 4 and tested on the 5th, five times. "
                         "The average error shows how well the model works on players it has not seen."),
    "rmse": ("RMSE (root mean squared error)",
             "A typical error size that punishes big mistakes more than small ones. Lower is better."),
    "mae": ("MAE (mean absolute error)",
            "The average size of the model's error, ignoring whether it was too high or too low. Lower is better."),
    "synthetic": ("Synthetic target",
                  "In this prototype the market values are generated from the statistics plus random noise, because real "
                  "Transfermarkt values are not yet loaded. They show that the pipeline works, not real prices."),
    "percentile": ("Percentile within position",
                   "The share of players in the same position with a lower value. 80 means better than 80% of players in that position."),
    "log value": ("Log value",
                  "The model predicts the logarithm of market value, because values are very skewed. Going from £10m to £20m then "
                  "counts the same as from £50m to £100m. The site converts back to pounds."),
    "shared strengths": ("Shared strengths",
                         "Statistics where both the target and the candidate are above the average for their position."),
    "xgboost": ("XGBoost",
                "A model made of many small decision trees, each one correcting the errors of the previous ones."),
    "random forest": ("Random Forest",
                      "An ensemble of independent decision trees trained on random subsets of players and features, averaging their predictions."),
    "linear regression": ("Linear Regression",
                          "A baseline model that predicts log market value as a weighted straight-line sum of the input features."),
    "dependence plot": ("SHAP dependence plot",
                        "A scatter plot on the Dashboard showing one feature on the horizontal axis and its SHAP effect on value on the vertical axis, with one dot per player coloured by position."),
    "radar chart": ("Player radar chart",
                    "An 8-spoke chart comparing up to 4 players across key attacking, creative, passing and defensive stats using percentiles within each player's own position (100 = best in position)."),
    "r2": ("R² (coefficient of determination)",
           "Measures the share of variance in log market values explained by the model (from 0 to 1, where 1 is a perfect fit). Higher is better."),
    "undervalued": ("Undervalued vs overvalued",
                    "A player is undervalued by the model when his model estimate exceeds his listed market value (above the dashed line on the Dashboard scatter), or when his estimate is lower than the median of his 5 closest statistical peers."),
    "confidence band": ("Confidence band",
                        "A typical uncertainty range around a player's estimate, computed by multiplying and dividing the estimate by exp(CV RMSE in log scale)."),
    "sus": ("SUS & Evaluation Console",
            "System Usability Scale (SUS) is a standard 10-question usability questionnaire scored from 0 to 100, available alongside accuracy ratings and task timings on the access-code-protected /eval page."),
}

GLOSSARY_ALIASES = {
    "per90": "per 90", "p90": "per 90", "per 90 minutes": "per 90", "/90": "per 90",
    "expected goals": "xg", "expected assists": "xa", "shapley": "shap", "shap values": "shap", "shap value": "shap",
    "waterfall chart": "waterfall", "cosine": "cosine similarity", "similarity": "cosine similarity",
    "similarity score": "cosine similarity", "zscore": "z score", "z scores": "z score",
    "price filter": "value filter", "maximum price": "value filter", "max price": "value filter",
    "out of fold estimate": "out of fold", "oof": "out of fold", "out of fold estimates": "out of fold",
    "team strength indicator": "team strength", "cv": "cross validation", "crossvalidation": "cross validation",
    "synthetic target": "synthetic", "synthetic values": "synthetic", "percentiles": "percentile",
    "log": "log value", "log market value": "log value", "shared strength": "shared strengths",
    "rf": "random forest", "ols": "linear regression", "dependence": "dependence plot",
    "radar": "radar chart", "r squared": "r2", "overvalued": "undervalued",
    "error band": "confidence band", "system usability scale": "sus", "evaluation console": "sus",
}

HOWTO = {
    "scout": ("How to run a scouting search", [
        "Open **Scout** in the top navigation bar.",
        "Type the target player's name and pick him from the list.",
        "Set the position (default: same as the target), the maximum price as % of his value (default 60%) and an age limit.",
        "Press **Find alternatives**. The table ranks candidates by similarity.",
        "Click a candidate to inspect his profile or radar comparison.",
    ], "/scout"),
    "waterfall": ("How to read a waterfall chart", [
        "Start at the **base value**: what the model predicts for an average player.",
        "Each bar is one feature. Green bars push the estimate up, red bars pull it down.",
        "Each row shows the exact pound impact added step-by-step from the base value.",
        "Base value plus all feature rows equals the final **Model Estimate**.",
        "Remember: it shows what the model uses, not what causes value.",
    ], "/dashboard"),
    "export": ("How to export a shortlist", [
        "Run a scouting search or ranking right here in chat (or on the Scout page).",
        "Click **Download CSV** or **Copy CSV** below any table in chat, or ask *export the shortlist*.",
    ], "/scout"),
    "compare": ("How to compare players", [
        "Open the **Compare** page (or ask *Compare Player A and Player B* here in chat).",
        "Add two to four players with the search box.",
        "Read the side-by-side table and the percentile radar chart.",
    ], "/compare"),
    "explain": ("How to see why a player is valued as he is", [
        "Search for the player on **Players** and open his profile, or select him in **Dashboard**.",
        "Check the **SHAP waterfall** breakdown to see which stats push his estimate up or down.",
        "For league-wide SHAP importance and dependence plots, open the **Dashboard** tab.",
    ], "/dashboard"),
    "search": ("How to find a player", [
        "Use the search box at the top of the **Players** page and start typing a name.",
        "Filter by club or position if you like, then click a player to open his profile.",
    ], "/players"),
    "rankings": ("How to see top lists", [
        "Open the **Rankings** page.",
        "Choose what to rank by (estimated value, goals, assists, xG, xA, minutes, pass completion %, tackles, or dribbles).",
        "Filter by position, age range and minimum minutes.",
    ], "/rankings"),
    "dashboard": ("How to use the Dashboard", [
        "Open **Dashboard** in the top navigation bar.",
        "Compare candidate models (`XGBoost`, `Random Forest`, `Linear Regression`) across R², log RMSE, log MAE and median % error.",
        "Explore the **Listed vs Estimated** scatter plot by position and age range — click any dot to inspect that player.",
        "Click any bar in **What drives valuations (SHAP)** to view its player-level dependence plot, filterable by position.",
        "Use the independent **SHAP Waterfall** and **Player Radar** panels below to inspect exact pound steps, percentiles and raw stats.",
    ], "/dashboard"),
}
