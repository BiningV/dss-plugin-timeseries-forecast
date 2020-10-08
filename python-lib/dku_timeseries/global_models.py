import pandas as pd
from dku_timeseries.single_model import SingleModel
from gluonts.dataset.common import ListDataset
try:
    from BytesIO import BytesIO  # for Python 2
except ImportError:
    from io import BytesIO  # for Python 3


class GlobalModels():
    def __init__(self, target_columns_names, time_column_name, frequency, model_folder, epoch, models_parameters, prediction_length, training_df, make_forecasts, external_features_column_name=None):
        self.models_parameters = models_parameters
        self.model_names = []
        self.models = None
        self.glutonts_dataset = None
        self.training_df = training_df
        self.prediction_length = prediction_length
        self.target_columns_names = target_columns_names
        self.time_col = time_column_name
        self.frequency = frequency
        self.model_folder = model_folder
        self.epoch = epoch
        self.make_forecasts = make_forecasts
        self.external_features_column_name = [] if external_features_column_name is None else external_features_column_name

    def init_all_models(self):
        self.models = []
        for model_name in self.models_parameters:
            model_parameters = self.models_parameters.get(model_name)
            self.models.append(
                SingleModel(
                    model_name,
                    model_parameters=model_parameters,
                    frequency=self.frequency,
                    prediction_length=self.prediction_length,
                    epoch=self.epoch
                )
            )
        if self.make_forecasts:
            self.forecasts_df = pd.DataFrame()

    def fit_all(self):
        # create list dataset for fit
        train_ds = self.create_gluonts_dataset(length=len(self.training_df.index))
        for model in self.models:
            model.fit(train_ds)

    def create_gluonts_dataset(self, length):
        initial_date = self.training_df[self.time_col].iloc[0]
        start = pd.Timestamp(initial_date, freq=self.frequency).tz_localize(None)
        #print("ALX:self.external_features_future_df={}".format(self.external_features_future_df))
        if self.external_features_column_name is None or len(self.external_features_column_name) == 0:
            return ListDataset(
                [{
                    "start": start,
                    "target": self.training_df[target_column_name].iloc[:length]  # start from 0 to length
                } for target_column_name in self.target_columns_names],
                freq=self.frequency
            )
        else:
            columns_names_to_drop = []
            columns_names_to_drop.append(self.time_col)
            columns_names_to_drop.extend(self.target_columns_names)
            print("ALX:columns_names_to_drop={}".format(columns_names_to_drop))
            #print("ALX:self.training_df={}".format(self.training_df))
            for col in self.training_df.columns:
                print("ALX:col={}".format(col))
            print("ALX:self.external_features_column_name={}".format(self.external_features_column_name))
            # for col in self.external_features_future_df.columns:
            #     print("ALX:col2={}".format(col))
            #external_features_all_df = self.training_df.drop(columns_names_to_drop).append(self.external_features_future_df.drop(self.time_col))
            external_features_all_df = self.training_df.drop(self.external_features_column_name, axis=1)
            print("ALX:external_features_all_df={}".format(external_features_all_df))
            return ListDataset(
                [{
                    "start": start,
                    "target": self.training_df[target_column_name].iloc[:length],  # start from 0 to length
                    'feat_dynamic_real': external_features_all_df.values.T
                } for target_column_name in self.target_columns_names],
                freq=self.frequency
            )

    def evaluate_all(self, evaluation_strategy):
        total_length = len(self.training_df.index)
        if evaluation_strategy == "split":
            train_ds = self.create_gluonts_dataset(length=total_length-self.prediction_length)  # all - prediction_length time steps
            test_ds = self.create_gluonts_dataset(length=total_length)  # all time steps
        else:
            raise Exception("{} evaluation strategy not implemented".format(evaluation_strategy))

        metrics_df = pd.DataFrame()
        for model in self.models:
            if self.make_forecast:
                agg_metrics, item_metrics, forecasts_df = model.evaluate_and_forecast(train_ds, test_ds)
                # TODO concat forecasts_df to others forecast_df and make it a class field
                self.forecasts_df = self.forecasts_df.merge(forecasts_df, on=self.time_col)
            else:
                agg_metrics, item_metrics = model.evaluate(train_ds, test_ds)

            item_metrics.insert(1, 'target_col', self.target_columns_names)
            agg_metrics['target_col'] = 'All'
            item_metrics = item_metrics.append(agg_metrics, ignore_index=True)

            metrics_df = metrics_df.append(item_metrics)
        return metrics_df

    def save_all(self, version_name):
        model_folder = self.model_folder
        for model in self.models:
            model.save(model_folder=model_folder, version_name=version_name)

    def prediction(self, model_name):
        return

    def load(self, path):
        # Todo
        dataset = load(dataset)
        best_model = find_best_model(dataset)
        model = SingleModel()
        model.load(path, best_model)

    def get_forecast_df(self):
        # TODO method to output all forecast and true values if self.forecast is True
        return self.training_df.merge(self.forecasts_df, on=self.time_col, how='left')
