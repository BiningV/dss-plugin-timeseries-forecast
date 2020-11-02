# import dill as pickle #todo: check whether or not dill still necessary
#  from gluonts.trainer import Trainer
from gluonts.model.naive_2 import Naive2Predictor
from plugin_io_utils import get_estimator, write_to_folder, EVALUATION_METRICS, get_trainer, METRICS_DATASET, get_predictor
from gluonts.evaluation.backtest import make_evaluation_predictions
from gluonts.evaluation import Evaluator
import pandas as pd
import logging


class SingleModel():
    def __init__(self, model_name, model_parameters, frequency, prediction_length, epoch):
        self.model_name = model_name
        self.model_parameters = model_parameters
        self.frequency = frequency
        self.prediction_length = prediction_length
        self.epoch = epoch
        estimator_kwargs = {
            "freq": self.frequency,
            "prediction_length": self.prediction_length
        }
        trainer = get_trainer(model_name, epochs=self.epoch)
        if trainer is not None:
            estimator_kwargs.update({"trainer": trainer})
        self.estimator = get_estimator(
            self.model_name,
            self.model_parameters,
            **estimator_kwargs
        )
        self.predictor = None
        if self.estimator is None:
            print("{} model is not implemented yet".format(model_name))

    def get_name(self):
        return self.model_name

    def fit(self, train_ds):
        if self.estimator is None:
            print("No training: {} model not implemented yet".format(self.model_name))
            return
        logging.info("Timeseries forecast - Training model {} on all data".format(self.model_name))
        self.predictor = self.estimator.train(train_ds)

    def evaluate(self, train_ds, test_ds, make_forecasts=False):
        logging.info("Timeseries forecast - Training model {} for evaluation".format(self.model_name))
        if self.estimator is None:
            predictor = get_predictor(self.model_name, freq=self.frequency, prediction_length=self.prediction_length)
        else:
            predictor = self.estimator.train(train_ds)
        evaluator = Evaluator()

        forecast_it, ts_it = make_evaluation_predictions(
            dataset=test_ds,  # test dataset
            predictor=predictor,  # predictor
            num_samples=100,  # number of sample paths we want for evaluation
        )
        ts_list = list(ts_it)
        forecast_list = list(forecast_it)

        agg_metrics, item_metrics = evaluator(iter(ts_list), iter(forecast_list), num_series=len(test_ds))

        item_metrics[METRICS_DATASET.MODEL_COLUMN] = self.model_name
        agg_metrics[METRICS_DATASET.MODEL_COLUMN] = self.model_name

        target_cols = [time_series['target'].name for time_series in train_ds.list_data]
        item_metrics[METRICS_DATASET.TARGET_COLUMN] = target_cols

        # if len(item_metrics.index) > 1:  # only display the aggregation row when multiple targets
        agg_metrics[METRICS_DATASET.TARGET_COLUMN] = METRICS_DATASET.AGGREGATED_ROW
        item_metrics = item_metrics.append(agg_metrics, ignore_index=True)

        item_metrics = item_metrics[[METRICS_DATASET.TARGET_COLUMN, METRICS_DATASET.MODEL_COLUMN] + EVALUATION_METRICS]

        if make_forecasts:
            series = []
            for i, sample_forecasts in enumerate(forecast_list):
                series.append(sample_forecasts.mean_ts.rename("{}_{}".format(target_cols[i], self.model_name)))
            forecasts_df = pd.concat(series, axis=1).reset_index()
            return agg_metrics, item_metrics, forecasts_df

        return agg_metrics, item_metrics

    def save(self, model_folder, version_name):  # todo: review how folder/paths are handled
        model_path = "{}/{}/model.pk.gz".format(version_name, self.model_name)
        write_to_folder(self.predictor, model_folder, model_path, 'pickle.gz')

        parameters_path = "{}/{}/params.json".format(version_name, self.model_name)
        write_to_folder(self.model_parameters, model_folder, parameters_path, 'json')

# file structure:
# Subfolder per timestamp (each time the recipe is run)
# -> CSV with all model results (same as output dataset)
# -> 1 subfolder per model
#   -> model.pk (Predictor object = estimator.train output)
#   -> params.json (local and global params, including external features)
# model_folder/versions/ts/output.csv
# model_folder/versions/ts/model-blaa/model.pk
# model_folder/versions/ts/model-blaa/params.json
