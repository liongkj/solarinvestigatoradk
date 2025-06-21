import json

from google.adk.tools.tool_context import ToolContext
import numpy as np
from google.adk.tools.base_tool import BaseTool
from typing import Dict, Any
import pandas as pd
from sklearn.ensemble import IsolationForest
from statsmodels.tsa.seasonal import seasonal_decompose


def append_problematic_rows(rows: str, tool_context: ToolContext):
    """tools to store problematic rows
    parameters
    String rows : the json response for the problematic five minutes data eg. "{problematic_five_minutes_pr : [row_data_here] ,analysis : "A general explaination on why you think these data is abnormal}"
    """
    if "problematic_five_minutes_pr" not in tool_context.state:
        problematic_five_minutes_pr_settings = []
        tool_context.state["problematic_five_minutes_pr"] = (
            problematic_five_minutes_pr_settings
        )

    problematic_five_minutes_pr_settings = tool_context.state[
        "problematic_five_minutes_pr"
    ]
    problematic_five_minutes_pr_settings.append(rows)
    tool_context.state["problematic_five_minutes_pr"] = (
        problematic_five_minutes_pr_settings
    )


async def filter_plant_timeseries_data(
    string_data: str, tool_context: ToolContext
) -> str:
    """
    Tools to filter the data, to extract possible abnormal data for further analysis

    args:
    string_data(str) :data to be filtered in string

    return:
    res(str) :filtered data in json string
    """
    data = json.loads(string_data)
    df = pd.DataFrame(data)
    # Prepare data
    df_work = df.copy()

    # Derived Features
    df_work["norm_power"] = df_work["active_power_effective_kw"] / df_work[
        "irradiance_wm_squared"
    ].replace(0, pd.NA)
    df_work["smoothed_power"] = (
        df_work["active_power_effective_kw"].rolling(window=12, min_periods=1).mean()
    )

    # Rule-based Detection
    df_work["low_yield"] = (df_work["irradiance_wm_squared"] > 400) & (
        df_work["five_min_pr_percent"] < 60
    )
    df_work["power_drop"] = pd.to_numeric(df_work["active_power_effective_kw"].diff(), errors="coerce") < -100
    df_work["clipping"] = (
        (pd.to_numeric(df_work["active_power_effective_kw"].diff().abs(), errors="coerce") < 1)
        & (df_work["irradiance_wm_squared"] > 900)
    )

    # Time Series Decomposition
    try:
        result = seasonal_decompose(
            df_work["active_power_effective_kw"].interpolate(),
            model="additive",
            period=48,
        )
        df_work["trend"] = result.trend
        df_work["seasonal"] = result.seasonal
        df_work["residual"] = result.resid
        residual_std = df_work["residual"].std()
        df_work["residual_anomaly"] = df_work["residual"].abs() > 3 * residual_std
    except:
        print("Warning: Seasonal decomposition failed, using simpler residual method")
        df_work["residual_anomaly"] = False

    # ML-Based Detection
    ml_features = df_work[
        ["norm_power", "five_min_pr_percent", "pv_module_temperature_c"]
    ].dropna()
    if len(ml_features) > 10:
        clf = IsolationForest(contamination=0.05, random_state=42)
        ml_predictions = clf.fit_predict(ml_features)
        df_work.loc[ml_features.index, "ml_anomaly"] = ml_predictions == -1
        # Fix the FutureWarning by using infer_objects
        df_work["ml_anomaly"] = (
            df_work["ml_anomaly"].fillna(False).infer_objects()
        )
    else:
        df_work["ml_anomaly"] = False

    # Combine flags
    df_work["production_final"] = df_work[
        ["low_yield", "power_drop", "clipping", "residual_anomaly", "ml_anomaly"]
    ].any(axis=1)

    production_anomalies = df_work[df_work["production_final"]]

    # Method 2: Exploratory Approach (Simplified)
    # Simple residual analysis
    power_values = df_work["active_power_effective_kw"].values
    window_size = max(5, len(power_values) // 20)
    trend = pd.Series(power_values).rolling(window=window_size, center=True).mean()
    trend = trend.bfill().ffill()
    residuals = power_values - trend

    # Statistical thresholds
    std_threshold = 1.5 * np.std(residuals)
    exploratory_mask = np.abs(residuals) > std_threshold

    # Add PR condition
    if "five_min_pr_percent" in df_work.columns:
        pr_mask = (df_work["irradiance_wm_squared"] > 400) & (
            df_work["five_min_pr_percent"] < 70
        )
        exploratory_mask = exploratory_mask | pr_mask

    df_work["exploratory_final"] = exploratory_mask
    exploratory_anomalies = df_work[exploratory_mask]

    # Combine the best aspects
    hybrid_conditions = []

    # From production method: specific domain rules
    hybrid_conditions.append(df_work["low_yield"])
    hybrid_conditions.append(df_work["power_drop"])

    # From exploratory method: statistical outliers
    df_work["stat_outlier"] = np.abs(residuals) > std_threshold
    hybrid_conditions.append(df_work["stat_outlier"])

    # ML component (if available)
    if "ml_anomaly" in df_work.columns:
        hybrid_conditions.append(df_work["ml_anomaly"])

    # Temperature-based (additional)
    if "pv_module_temperature_c" in df_work.columns:
        temp_outlier = df_work["pv_module_temperature_c"] > df_work[
            "pv_module_temperature_c"
        ].quantile(0.95)
        hybrid_conditions.append(temp_outlier)

    df_work["hybrid_final"] = pd.concat(hybrid_conditions, axis=1).any(axis=1)
    hybrid_anomalies = df_work[df_work["hybrid_final"]]

    # Fix column selection (was duplicated)
    filtered_df = hybrid_anomalies[
        [
            "datetime",
            "five_min_pr_percent",
            "active_power_effective_kw",
            "irradiance_wm_squared",
            "pv_module_temperature_c",
        ]
    ]

    # CRITICAL FIX: Convert DataFrames to serializable format
    # Convert to dictionary/JSON format to avoid serialization error
    print(filtered_df)
    tool_context.state["filtered_plant_timeseries_df"] = filtered_df.to_json(
        orient="records"
    )
    res = filtered_df.to_json(orient="records")
    return res
