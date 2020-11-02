import pandas as pd
from dku_timeseries.single_model import SingleModel
from gluonts.dataset.common import ListDataset
from plugin_io_utils import write_to_folder, METRICS_DATASET


class GlobalModels():
    def __init__(self, target_columns_names, time_column_name, frequency, model_folder, epoch, models_parameters, prediction_length,
                 training_df, make_forecasts, external_features_columns_names=None, timeseries_identifiers_names=None):
        self.models_parameters = models_parameters
        self.model_names = []
        self.models = None
        self.glutonts_dataset = None
        self.training_df = training_df
        self.prediction_length = prediction_length
        self.target_columns_names = target_columns_names
        self.time_column_name = time_column_name
        self.frequency = frequency
        self.model_folder = model_folder
        self.epoch = epoch
        self.make_forecasts = make_forecasts
        self.external_features_columns_names = external_features_columns_names
        self.use_external_features = (len(external_features_column_names) > 0)
        self.timeseries_identifiers_names = timeseries_identifiers_names

    def init_all_models(self, version_name):
        self.version_name = version_name
        self.models = []
        for model_name in self.models_parameters:
            model_parameters = self.models_parameters.get(model_name)
            self.models.append(
                SingleModel(
                    model_name,
                    model_parameters=model_parameters,
                    frequency=self.frequency,
                    prediction_length=self.prediction_length,
                    epoch=self.epoch,
                    use_external_features=self.use_external_features
                )
            )
        # already done in assert_continuous_time_column
        # self.training_df[self.time_column_name] = pd.to_datetime(self.training_df[self.time_column_name]).dt.tz_localize(tz=None)
        if self.make_forecasts:
            self.forecasts_df = pd.DataFrame()

    def fit_all(self):
        # create list dataset for fit
        # train_ds = self.create_gluonts_dataset()
        for model in self.models:
            model.fit(self.test_ds)

    def create_gluon_dataset(self, remove_length=None):
        length = -remove_length if remove_length else None
        multivariate_timeseries = []
        print("self.timeseries_identifiers_names: ", self.timeseries_identifiers_names)
        if self.timeseries_identifiers_names:
            print("it's true")
            for identifiers_names, identifiers_df in self.training_df.groupby(self.timeseries_identifiers_names):
                multivariate_timeseries += self._create_gluon_multivariate_timeseries(identifiers_df, length, identifiers_names=identifiers_names)
        else:
            multivariate_timeseries += self._create_gluon_multivariate_timeseries(self.training_df, length)
        # return multivariate_timeseries
        return ListDataset(multivariate_timeseries, freq=self.frequency)

    def _create_gluon_multivariate_timeseries(self, df, length, identifiers_names=None):
        multivariate_timeseries = []
        for target_column_name in self.target_columns_names:
            multivariate_timeseries.append(self._create_gluon_univariate_timeseries(df, target_column_name, length, identifiers_names))
        return multivariate_timeseries
    
    def _create_gluon_univariate_timeseries(self, df, target_column_name, length, identifiers_names=None):
        """ create dictionary for one timeseries and add extra features and identifiers if specified """
        univariate_timeseries = {
            'start': df[self.time_column_name].iloc[0],
            'target': df[target_column_name].iloc[:length].values,
            'target_name': target_column_name
        }
        if self.external_features_columns_names:
            univariate_timeseries['feat_dynamic_real'] = df[self.external_features_columns_names].iloc[:length]
        if identifiers_names:
            identifiers_map = {self.timeseries_identifiers_names[i]: identifier_name for i, identifier_name in enumerate(identifiers_names)}
            univariate_timeseries['identifiers'] = identifiers_map
        return univariate_timeseries
            
    # def create_gluon_dataset_from_wide_format(self, length):
    #     initial_date = self.training_df[self.time_column_name].iloc[0]
    #     start = pd.Timestamp(initial_date, freq=self.frequency)
    #     if not self.external_features_columns_names:
    #         return ListDataset(
    #             [{
    #                 "start": start,
    #                 "target": self.training_df[target_column_name].iloc[:length].values,  # start from 0 to length
    #                 "target_name": target_column_name
    #             } for target_column_name in self.target_columns_names],
    #             freq=self.frequency
    #         )
    #     else:
    #         external_features_all_df = self.training_df[self.external_features_columns_names].iloc[:length]
    #         return ListDataset(
    #             [{
    #                 'start': start,
    #                 'target': self.training_df[target_column_name].iloc[:length].values,  # start from 0 to length
    #                 'feat_dynamic_real': external_features_all_df.values.T
    #             } for target_column_name in self.target_columns_names],
    #             freq=self.frequency
    #         )
    
    # def create_gluon_dataset_from_long_format(self, length):
    #     """ convert training_df into ListDataset based on category columns """
    #     multiple_timeseries = []
    #     for identifiers_names, identifiers_df in self.training_df.groupby(self.timeseries_identifiers_names):
    #         identifiers_map = {self.timeseries_identifiers_names[i]: group_name for i, group_name in enumerate(identifiers_names)}
    #         identifiers_label = '_'.join([f"{self.timeseries_identifiers_names[i]}_{group_name}" for i, group_name in enumerate(identifiers_names)])
    #         for target_column_name in self.target_columns_names:
    #             timeseries = {
    #                 'start': identifiers_df[self.time_column_name].iloc[0],
    #                 'target': identifiers_df[target_column_name].iloc[:length].values,
    #                 'target_name': f"{target_column_name}_{identifiers_label}",
    #                 'target_column_name': target_column_name,
    #                 'identifiers': identifiers_map
    #             }
    #             multiple_timeseries.append(timeseries)
    #     return ListDataset(multiple_timeseries, freq=self.frequency)

    def evaluate_all(self, evaluation_strategy):
        # total_length = len(self.training_df.index)
        if evaluation_strategy == "split":
            self.train_ds = self.create_gluon_dataset(remove_length=self.prediction_length)  # remove last prediction_length time steps
            self.test_ds = self.create_gluon_dataset()  # all time steps
        else:
            raise Exception("{} evaluation strategy not implemented".format(evaluation_strategy))
        self.metrics_df = self._compute_all_evaluation_metrics()
        print("metrics_df.columns in evaluate_all: ", self.metrics_df.columns)
        print("metrics_df.describe() in evaluate_all: ", self.metrics_df.describe())

    def _compute_all_evaluation_metrics(self):
        metrics_df = pd.DataFrame()
        for model in self.models:
            if self.make_forecasts:
                # if self.timeseries_identifiers_names:
                #     raise ValueError("Cannot output evaluation forecasts dataset with long format input.")
                agg_metrics, item_metrics, forecasts_df, identifiers_columns = model.evaluate(self.train_ds, self.test_ds, make_forecasts=True)
                forecasts_df = forecasts_df.rename(columns={'time_column': self.time_column_name})
                if self.forecasts_df.empty:
                    self.forecasts_df = forecasts_df
                else:
                    self.forecasts_df = self.forecasts_df.merge(forecasts_df, on=[self.time_column_name] + identifiers_columns)
            else:
                agg_metrics, item_metrics = model.evaluate(self.train_ds, self.test_ds)
            metrics_df = metrics_df.append(item_metrics)
        metrics_df['session'] = self.version_name
        orderd_metrics_df = self._reorder_metrics_df(metrics_df)
        
        if self.make_forecasts:
            self.evaluation_forecasts_df = self.training_df.merge(self.forecasts_df, on=[self.time_column_name] + identifiers_columns, how='left')
            self.evaluation_forecasts_df['session'] = self.version_name

        return orderd_metrics_df

    def _reorder_metrics_df(self, metrics_df):
        """ sort rows by target column and put aggregated rows on top """
        metrics_df = metrics_df.sort_values(by=[METRICS_DATASET.TARGET_COLUMN], ascending=True)
        orderd_metrics_df = pd.concat([
            metrics_df[metrics_df[METRICS_DATASET.TARGET_COLUMN]==METRICS_DATASET.AGGREGATED_ROW],
            metrics_df[metrics_df[METRICS_DATASET.TARGET_COLUMN]!=METRICS_DATASET.AGGREGATED_ROW]
        ], axis=0).reset_index(drop=True)
        return orderd_metrics_df

    def save_all(self):
        metrics_path = "{}/metrics.csv".format(self.version_name)
        write_to_folder(self.metrics_df, self.model_folder, metrics_path, 'csv')

        gluon_train_dataset_path = "{}/gluon_train_dataset.pickle.gz".format(self.version_name)
        write_to_folder(self.test_ds, self.model_folder, gluon_train_dataset_path, 'pickle.gz')

        # targets_df_path = "{}/targets_train_dataset.csv.gz".format(self.version_name)
        # write_to_folder(self.training_df[[self.time_column_name]+self.target_columns_names], self.model_folder, targets_df_path, 'csv.gz')

        # if self.external_features_columns_names:
        #     external_features_df_path = "{}/external_features_train_dataset.csv.gz".format(self.version_name)
        #     write_to_folder(self.training_df[[self.time_column_name]+self.external_features_columns_names], self.model_folder, external_features_df_path, 'csv.gz')

        for model in self.models:
            model.save(model_folder=self.model_folder, version_name=self.version_name)

    def get_evaluation_forecasts_df(self):
        # self.evaluation_forecasts_df = self.training_df.merge(self.forecasts_df, on=self.time_column_name, how='left')
        # self.evaluation_forecasts_df['session'] = self.version_name
        return self.evaluation_forecasts_df

    def get_metrics_df(self):
        return self.metrics_df

    def create_metrics_column_description(self):
        column_descriptions = {}
        for column in self.metrics_df.columns:
            column_descriptions[column] = "TO FILL"
        return column_descriptions

    def create_evaluation_forecasts_column_description(self):
        column_descriptions = {}
        for column in self.evaluation_forecasts_df.columns:
            column_descriptions[column] = "TO FILL"
        return column_descriptions
