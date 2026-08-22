from __future__ import annotations

import pandas as pd

from training.outs_opponent_pressure_capture import FIRST_ELIGIBLE_GAME_DATE, LEAGUE_K_RATE, LEAGUE_OBP

VERSION = "outs-opponent-pressure-preregistration-v1"
PREREGISTERED_GAME_DATE = "2026-08-22"
REPORT_ONLY = True
PRODUCTION_AUTHORITY = "NONE"
NO_PROJECTION_ADJUSTMENT = True
NO_AUTO_PROMOTION = True
AUTOMATIC_DECISION_ALLOWED = False
SUPPORTING_DIAGNOSTIC_ONLY = True
PROMOTION_ROW_REGISTERED = False

MIN_GLOBAL_RESOLVED_STARTS = 60
MIN_GLOBAL_RESOLVED_DAYS = 10
MIN_GLOBAL_PITCHERS = 20
MIN_GLOBAL_OPPONENTS = 15
MIN_SOURCE_COVERAGE = 0.95
MIN_RULE_STARTS = 15
OUTS_RESIDUAL_EFFECT_THRESHOLD = 0.75
HIGH_OBP_THRESHOLD = 0.335
HIGH_CONTACT_THRESHOLD = 0.800

RULES = (
    ("OBP_HIGH_335_PLUS", "pregame opponent OBP vs pitcher hand >= 0.335", "Opponent_OBP", "LOWER_OUTS_RESIDUAL"),
    ("CONTACT_HIGH_800_PLUS", "pregame opponent contact rate vs pitcher hand >= 0.800", "Opponent_Contact_Rate", "EXPLORATORY_DIRECTIONAL"),
    ("OBP335_AND_CONTACT800", "opponent OBP >= 0.335 AND contact rate >= 0.800", "Opponent_OBP;Opponent_Contact_Rate", "LOWER_OUTS_RESIDUAL"),
)

COLUMNS = [
    "Preregistration_Version", "Preregistered_Game_Date", "First_Eligible_Game_Date",
    "Rule_ID", "Rule_Definition", "Primary_Field", "Expected_Direction",
    "Primary_Outcome", "Primary_Effect", "League_K_Prior", "League_OBP_Prior",
    "High_OBP_Threshold", "High_Contact_Threshold", "Rule_Min_Starts",
    "Global_Min_Starts", "Global_Min_Days", "Global_Min_Pitchers",
    "Global_Min_Opponents", "Min_Source_Coverage", "Material_Effect_Threshold_Outs",
    "Selection_Basis", "Report_Only", "Production_Authority",
    "No_Projection_Adjustment", "No_Auto_Promotion", "Automatic_Decision_Allowed",
    "Supporting_Diagnostic_Only", "Promotion_Row_Registered",
]


def build_preregistration() -> pd.DataFrame:
    rows = []
    for rule_id, definition, field, direction in RULES:
        rows.append({
            "Preregistration_Version": VERSION,
            "Preregistered_Game_Date": PREREGISTERED_GAME_DATE,
            "First_Eligible_Game_Date": FIRST_ELIGIBLE_GAME_DATE,
            "Rule_ID": rule_id,
            "Rule_Definition": definition,
            "Primary_Field": field,
            "Expected_Direction": direction,
            "Primary_Outcome": "exact frozen starter-outs residual",
            "Primary_Effect": "flagged mean residual minus unflagged mean residual",
            "League_K_Prior": LEAGUE_K_RATE,
            "League_OBP_Prior": LEAGUE_OBP,
            "High_OBP_Threshold": HIGH_OBP_THRESHOLD,
            "High_Contact_Threshold": HIGH_CONTACT_THRESHOLD,
            "Rule_Min_Starts": MIN_RULE_STARTS,
            "Global_Min_Starts": MIN_GLOBAL_RESOLVED_STARTS,
            "Global_Min_Days": MIN_GLOBAL_RESOLVED_DAYS,
            "Global_Min_Pitchers": MIN_GLOBAL_PITCHERS,
            "Global_Min_Opponents": MIN_GLOBAL_OPPONENTS,
            "Min_Source_Coverage": MIN_SOURCE_COVERAGE,
            "Material_Effect_Threshold_Outs": OUTS_RESIDUAL_EFFECT_THRESHOLD,
            "Selection_Basis": "Frozen before first eligible outcome. True OBP is primary; contact remains independently evaluated because its direction is not assumed.",
            "Report_Only": REPORT_ONLY,
            "Production_Authority": PRODUCTION_AUTHORITY,
            "No_Projection_Adjustment": NO_PROJECTION_ADJUSTMENT,
            "No_Auto_Promotion": NO_AUTO_PROMOTION,
            "Automatic_Decision_Allowed": AUTOMATIC_DECISION_ALLOWED,
            "Supporting_Diagnostic_Only": SUPPORTING_DIAGNOSTIC_ONLY,
            "Promotion_Row_Registered": PROMOTION_ROW_REGISTERED,
        })
    return pd.DataFrame(rows, columns=COLUMNS)
