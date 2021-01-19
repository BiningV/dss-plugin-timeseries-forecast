import pandas as pd
from pandas.tseries.frequencies import to_offset
import numpy as np
from functools import reduce
import copy
from constants import TIMESERIES_KEYS, ROW_ORIGIN, CUSTOMISABLE_FREQUENCIES_OFFSETS, GPU_CONFIGURATION
from timeseries_preparation.preparation import TimeseriesPreparator


def apply_filter_conditions(df, conditions):
    """Apply filter conditions on df.

    Args:
        df (DataFrame): Dataframe to filter.
        conditions (list): List of DataFrame filtering conditions on df.

    Returns:
        Filtered DataFrame.
    """
    if len(conditions) == 0:
        return df
    elif len(conditions) == 1:
        return df[conditions[0]]
    else:
        return df[reduce(lambda c1, c2: c1 & c2, conditions[1:], conditions[0])]


def add_future_external_features(gluon_train_dataset, external_features_future_df, prediction_length, frequency):
    """Append the future external features to the 'feat_dynamic_real' arrays of each timeseries of the ListDataset used for training.
    First check that all timeseries are valid (regular time steps of the chosen frequency and they all have the same start date).

    Args:
        gluon_train_dataset (gluonts.dataset.common.ListDataset): ListDataset created with the GluonDataset class.
        external_features_future_df (DataFrame): Dataframe of future (dated after timeseries of gluon_train_dataset) external features.
        prediction_length (int): To check that external_features_future_df has the right length.
        frequency (str): To check that the time column has the right frequency and values.

    Raises:
        ValueError: If the length of external_features_future_df is not prediction_length.

    Returns:
        gluonts.dataset.common.ListDataset with future external features.
    """
    gluon_dataset = copy.deepcopy(gluon_train_dataset)
    if isinstance(to_offset(frequency), CUSTOMISABLE_FREQUENCIES_OFFSETS):
        frequency = gluon_train_dataset.process.trans[0].freq

    start_date, periods = None, None
    for i, timeseries in enumerate(gluon_train_dataset):
        if TIMESERIES_KEYS.IDENTIFIERS in timeseries:
            # filter the dataframe to only get rows with the right identifiers
            timeseries_identifiers = timeseries[TIMESERIES_KEYS.IDENTIFIERS]
            conditions = [external_features_future_df[k] == v for k, v in timeseries_identifiers.items()]
            timeseries_external_features_future_df = apply_filter_conditions(external_features_future_df, conditions)
        else:
            timeseries_external_features_future_df = external_features_future_df

        feat_dynamic_real_train = timeseries[TIMESERIES_KEYS.FEAT_DYNAMIC_REAL]
        feat_dynamic_real_columns_names = timeseries[TIMESERIES_KEYS.FEAT_DYNAMIC_REAL_COLUMNS_NAMES]
        time_column_name = timeseries[TIMESERIES_KEYS.TIME_COLUMN_NAME]

        timeseries_preparator = TimeseriesPreparator(
            time_column_name=time_column_name,
            frequency=frequency,
        )
        timeseries_external_features_future_df = timeseries_preparator.prepare_timeseries_dataframe(timeseries_external_features_future_df)

        feat_dynamic_real_future = timeseries_external_features_future_df[feat_dynamic_real_columns_names].values.T

        if feat_dynamic_real_future.shape[1] != prediction_length:
            raise ValueError(f"Please provide {prediction_length} future values of external features, as this was the forecasting horizon used for training")

        feat_dynamic_real_appended = np.append(feat_dynamic_real_train, feat_dynamic_real_future, axis=1)

        gluon_dataset.list_data[i][TIMESERIES_KEYS.FEAT_DYNAMIC_REAL] = feat_dynamic_real_appended

    return gluon_dataset


def concat_timeseries_per_identifiers(all_timeseries):
    """Concatenate on columns all forecasts timeseries with same identifiers.

    Args:
        all_timeseries (dict): Dictionary of timeseries (value) by identifiers dictionary (key).

    Returns:
        List of timeseries with multiple forecasts for each identifiers.
    """
    multiple_df = []
    for timeseries_identifier_key, series_list in all_timeseries.items():
        unique_identifiers_df = pd.concat(series_list, axis=1).reset_index(drop=False)
        if timeseries_identifier_key:
            for identifier_key, identifier_value in timeseries_identifier_key:
                unique_identifiers_df[identifier_key] = identifier_value
        multiple_df += [unique_identifiers_df]
    return multiple_df


def concat_all_timeseries(multiple_df):
    """Concatenate on rows all forecasts timeseries (one identifiers timeseries after the other).

    Args:
        multiple_df (list): List of multivariate timeseries DataFrame with identifiers columns.

    Returns:
        DataFrame of multivariate long format timeseries.
    """
    return pd.concat(multiple_df, axis=0).reset_index(drop=True)


def add_row_origin(df, both, left_only):
    """Add an extra column that tells if the row is a forecast or historical data and return the new dataframe"""
    df_copy = df.copy()
    if "_merge" in df_copy:
        df_copy["_merge"] = df_copy["_merge"].replace({"both": both, "left_only": left_only})
        df_copy = df_copy.rename(columns={"_merge": ROW_ORIGIN.COLUMN_NAME})
    else:
        df_copy[ROW_ORIGIN.COLUMN_NAME] = both
    return df_copy


def quantile_forecasts_series(sample_forecasts, quantile, frequency):
    sample_forecasts_quantile = sample_forecasts.quantile(quantile)
    index = pd.date_range(sample_forecasts.start_date, periods=len(sample_forecasts_quantile), freq=frequency)
    return pd.Series(index=index, data=sample_forecasts_quantile)


class GPUError(Exception):
    """Custom exception raised when the GPU selection failed"""

    pass


def set_mxnet_context(gpu_devices):
    try:
        import mxnet as mx
    except OSError as cuda_error:  # error when importing mxnet
        raise GPUError(f"Error when importing mxnet: {cuda_error}")

    if gpu_devices is None:
        return mx.context.cpu()
    else:
        try:
            num_gpu = mx.context.num_gpus()
        except mx.base.MXNetError as num_gpus_error:  # error on num_gpus()
            raise GPUError(f"Error when querying number of GPU: {num_gpus_error}")

        if num_gpu == 0:
            if GPU_CONFIGURATION.CONTAINER_GPU in gpu_devices:
                raise GPUError("No GPU detected, please check that the container has GPUs")
            else:
                raise GPUError("No GPU detected, please check your server has GPUs")
        else:
            if GPU_CONFIGURATION.CONTAINER_GPU in gpu_devices:
                return mx.context.gpu(0)  # return first GPU of container
            else:
                return mx.context.gpu(gpu_devices[0])
