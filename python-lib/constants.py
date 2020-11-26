class METRICS_DATASET:
    """ Class of constants with labels used in the evaluation metrics dataframe of the train recipe """

    TARGET_COLUMN = "target_column"
    MODEL_COLUMN = "model"
    AGGREGATED_ROW = "aggregated"
    MODEL_PARAMETERS = "model_params"
    SESSION = "training_session"


class TIMESERIES_KEYS:
    """ Class of constants with labels for the keys used in the timeseries of the GluonDataset class """

    START = "start"
    TARGET = "target"
    TARGET_NAME = "target_name"
    TIME_COLUMN_NAME = "time_column_name"
    FEAT_DYNAMIC_REAL = "feat_dynamic_real"
    FEAT_DYNAMIC_REAL_COLUMNS_NAMES = "feat_dynamic_real_columns_names"
    IDENTIFIERS = "identifiers"


EVALUATION_METRICS_DESCRIPTIONS = {
    "mse": "Mean Squared Error",
    "mase": "Mean Absolute Scaled Error",
    "mape": "Mean Absolute Percentage Error",
    "smape": "Symmetric Mean Absolute Percentage Error",
    "msis": "Mean Scaled Interval Score",
    "rmse": "Root Mean Square Error",
    "normalized_deviation": "Normalized Deviation",
    "mean_wquantileloss": "Mean Weight Quantile Loss",
}


METRICS_COLUMNS_DESCRIPTIONS = {
    METRICS_DATASET.MODEL_PARAMETERS: "Parameters used for training",
    METRICS_DATASET.SESSION: "Timestamp of training session",
    METRICS_DATASET.TARGET_COLUMN: "Aggregated and per-time-series metrics",
}

# regex pattern to match the timestamps used for training sessions
TIMESTAMP_REGEX_PATTERN = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{6}Z"


TIME_DIMENSION_PATTERNS = {
        "DKU_DST_YEAR": "%Y",
        "DKU_DST_MONTH": "%M",
        "DKU_DST_DAY": "%D",
        "DKU_DST_HOUR": "%H"
    }


FORECASTING_STYLE_PRESELECTED_MODELS = {
        "auto": ["naive", "deepar"],
        "auto_performance": ["naive", "deepar", "transformer", "mqcnn"]
    }
