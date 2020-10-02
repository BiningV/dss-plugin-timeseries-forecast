import pandas as pd
from gluonts.dataset.common import ListDataset


class Prediction():
    def __init__(self, predictor, forecasting_horizon, confidence_intervals):
        self.predictor = predictor
        self.forecasting_horizon = forecasting_horizon
        self.confidence_intervals = confidence_intervals

        if predictor.prediction_length < forecasting_horizon:
            raise ValueError("Forecasting horizon cannot be higher than the prediction length ({}) used in training !".format(predictor.prediction_length))

    def predict(self, context_df, external_features_future_df=None):

        prediction_input = self._create_prediction_input(context_df, external_features_future_df)

        forecasts = self.predictor.predict(prediction_input)
        sample_forecasts = list(forecasts)[0]

        columns = ["forecasts"]
        series = [sample_forecasts.mean_ts]
        for conf_int in self.confidence_intervals:
            columns += ["quantile_{}".format(conf_int)]
            series += [sample_forecasts.quantile_ts(conf_int)]

        df = pd.concat(series, axis=1).reset_index()
        df.columns = [self.time_col] + columns

        if external_features_future_df:
            df = df.merge(external_features_future_df, on=self.time_col)

        predictions_df = df.iloc[:self.forecasting_horizon]

        # for nice plots !
        context_df["forecasts"] = context_df[self.target_col]

        self.results_df = context_df.append(predictions_df)

    def get_results_dataframe(self):
        return self.results_df

    def _create_prediction_input(self, context_df, external_features_future_df=None):
        """
        check that the external_features_future_df time series follows the df time series
        check they both have the same features columns
        check external_features_future_df has forecasting_horizon rows
        """
        # only column of context_df with datetime dtype (maybe assert that it's true), should always be the first column of context_df
        self.time_col = context_df.columns[0]  # assert it is a datetime

        try:
            context_df[self.time_col] = pd.to_datetime(context_df[self.time_col]) 
        except:
            raise ValueError("Could not convert to datetime !")

        # if no external features, then it's the other column, should always be the second column of context_df
        self.target_col = context_df.columns[1]

        if external_features_future_df:
            # if external features, then all must equal (external_df, prediction_length, forecasting_horizon)
            assert len(external_features_future_df.index) == self.predictor.prediction_length

            assert set(context_df.columns.drop(self.target_col)) == set(external_features_future_df.columns)
            # maybe also check for identical dtypes
            # external_features_cols = list(external_features_future_df.columns.drop(self.time_col))
            # external_features_all_df = context_df[external_features_cols].append(external_features_future_df[external_features_cols])
            external_features_all_df = context_df.drop([self.time_col, self.target_col]).append(external_features_future_df.drop(self.time_col))

            input_ds = ListDataset(
                [{
                    'target': context_df[self.target_col],
                    'feat_dynamic_real': external_features_all_df.values.T,
                    'start': context_df.iloc[0][self.time_col]
                }],
                freq=self.predictor.freq)
        else:
            input_ds = ListDataset(
                [{
                    'target': context_df[self.target_col],
                    'start': context_df.iloc[0][self.time_col]
                }],
                freq=self.predictor.freq)

        return input_ds
