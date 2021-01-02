from constants import EVALUATION_METRICS_DESCRIPTIONS, METRICS_DATASET, TIMESERIES_KEYS
from gluonts.evaluation.backtest import make_evaluation_predictions
from gluonts.evaluation import Evaluator
from gluonts_forecasts.model_handler import ModelHandler
from gluonts_forecasts.utils import concat_timeseries_per_identifiers, concat_all_timeseries
from time import perf_counter
from safe_logger import SafeLogger
import json

logger = SafeLogger("Forecast plugin")


class ModelTrainingError(Exception):
    """Custom exception raised when the model training fails"""

    pass


class Model(ModelHandler):
    """
    Wrapper class to train and evaluate a GluonTS estimator, and retrieve the evaluation metrics and predictions

    Attributes:
        model_name (str): Model name belonging to model_handler.MODEL_DESCRIPTORS
        model_parameters (dict): Kwargs of model parameters
        frequency (str): Pandas timeseries frequency (e.g. '3M')
        prediction_length (int): Number of time steps to predict
        epoch (int): Number of epochs used by the GluonTS Trainer class
        use_external_features (bool)
        batch_size (int): Size of batch used by the GluonTS Trainer class
        gpu (str): Not implemented
        context_length (int): Number of time steps used by model to make predictions
    """

    def __init__(
        self,
        model_name,
        model_parameters,
        frequency,
        prediction_length,
        epoch,
        use_external_features=False,
        batch_size=None,
        num_batches_per_epoch=None,
        gpu=None,
        context_length=None,
        cardinality=None,
    ):
        super().__init__(model_name)
        self.model_name = model_name
        self.model_parameters = model_parameters
        self.frequency = frequency
        self.prediction_length = prediction_length
        self.context_length = context_length
        self.epoch = epoch
        self.use_external_features = use_external_features

        self.using_external_features = False
        self.cardinality = cardinality
        self.using_feat_static_cat = False

        estimator_kwargs = {
            "freq": self.frequency,
            "prediction_length": self.prediction_length,
        }
        trainer_kwargs = {"epochs": self.epoch}
        self.batch_size = batch_size
        if self.batch_size is not None:
            trainer_kwargs.update({"batch_size": self.batch_size})
        self.num_batches_per_epoch = num_batches_per_epoch
        if self.num_batches_per_epoch is not None:
            trainer_kwargs.update({"num_batches_per_epoch": self.num_batches_per_epoch})
        trainer = ModelHandler.trainer(self, **trainer_kwargs)
        if trainer is not None:
            estimator_kwargs.update({"trainer": trainer})
        if ModelHandler.can_use_external_feature(self) and self.use_external_features:
            self.using_external_features = True
            estimator_kwargs.update({"use_feat_dynamic_real": True})
        if ModelHandler.can_use_feat_static_cat(self) and self.cardinality:
            self.using_feat_static_cat = True
            estimator_kwargs.update({"use_feat_static_cat": True})
            estimator_kwargs.update({"cardinality": self.cardinality})
        if self.context_length is not None and ModelHandler.can_use_context_length(self):
            estimator_kwargs.update({"context_length": self.context_length})
        self.estimator = ModelHandler.estimator(self, self.model_parameters, **estimator_kwargs)
        self.predictor = None
        self.evaluation_time = None

    def get_name(self):
        return self.model_name

    def train(self, train_list_dataset):
        start = perf_counter()
        logger.info(f"Training {self.get_label()} model...")
        self.predictor = self._train_estimator(train_list_dataset)
        logger.info(f"Training {self.get_label()} model: Done in {perf_counter() - start:.2f} seconds")

    def evaluate(self, train_list_dataset, test_list_dataset, make_forecasts=False):
        """Train Model on train_list_dataset and evaluate it on test_list_dataset.

        Args:
            train_list_dataset (gluonts.dataset.common.ListDataset): ListDataset created with the GluonDataset class.
            test_list_dataset (gluonts.dataset.common.ListDataset): ListDataset created with the GluonDataset class.
            make_forecasts (bool, optional): [description]. Defaults to False.

        Returns:
            Evaluation metrics DataFrame for each target and aggregated.
            List of timeseries identifiers column names. Empty list if none found in train_list_dataset.
            DataFrame of predictions for the last prediction_length timesteps of the test_list_dataset timeseries if make_forecasts is True.
        """
        logger.info(f"Evaluating {self.get_label()} model performance...")
        start = perf_counter()
        evaluation_predictor = self._train_estimator(train_list_dataset)

        agg_metrics, item_metrics, forecasts = self._make_evaluation_predictions(evaluation_predictor, test_list_dataset)
        self.evaluation_time = perf_counter() - start
        logger.info(f"Evaluating {self.get_label()} model performance: Done in {perf_counter() - start:.2f} seconds")

        metrics, identifiers_columns = self._format_metrics(agg_metrics, item_metrics, train_list_dataset)

        if make_forecasts:
            mean_forecasts_timeseries = self._compute_mean_forecasts_timeseries(forecasts, train_list_dataset)
            multiple_df = concat_timeseries_per_identifiers(mean_forecasts_timeseries)
            forecasts_df = concat_all_timeseries(multiple_df)
            return metrics, identifiers_columns, forecasts_df

        return metrics, identifiers_columns

    def _make_evaluation_predictions(self, predictor, test_list_dataset):
        """Evaluate predictor and generate sample forecasts.

        Args:
            predictor (gluonts.model.predictor.Predictor): Trained object used to make forecasts.
            test_list_dataset (gluonts.dataset.common.ListDataset): ListDataset created with the GluonDataset class.

        Returns:
            Dictionary of aggregated metrics over all timeseries.
            DataFrame of metrics for each timeseries (i.e., each target column).
            List of gluonts.model.forecast.Forecast (objects storing the predicted distributions as samples).
        """
        forecast_it, ts_it = make_evaluation_predictions(dataset=test_list_dataset, predictor=predictor, num_samples=100)
        timeseries = list(ts_it)
        forecasts = list(forecast_it)
        evaluator = Evaluator()
        agg_metrics, item_metrics = evaluator(iter(timeseries), iter(forecasts), num_series=len(test_list_dataset))
        return agg_metrics, item_metrics, forecasts

    def _format_metrics(self, agg_metrics, item_metrics, train_list_dataset):
        """Append agg_metrics to item_metrics and add new columns: model_name, target_column, identifiers_columns

        Args:
            agg_metrics (dict): Dictionary of aggregated metrics over all timeseries.
            item_metrics (DataFrame): [description]
            train_list_dataset (gluonts.dataset.common.ListDataset): ListDataset created with the GluonDataset class.

        Returns:
            DataFrame of metrics, model name, target column and identifiers columns.
        """
        item_metrics[METRICS_DATASET.MODEL_COLUMN] = ModelHandler.get_label(self)
        agg_metrics[METRICS_DATASET.MODEL_COLUMN] = ModelHandler.get_label(self)

        identifiers_columns = (
            list(train_list_dataset.list_data[0][TIMESERIES_KEYS.IDENTIFIERS].keys()) if TIMESERIES_KEYS.IDENTIFIERS in train_list_dataset.list_data[0] else []
        )
        identifiers_values = {identifiers_column: [] for identifiers_column in identifiers_columns}
        target_columns = []
        for univariate_timeseries in train_list_dataset.list_data:
            target_columns += [univariate_timeseries[TIMESERIES_KEYS.TARGET_NAME]]
            for identifiers_column in identifiers_columns:
                identifiers_values[identifiers_column] += [univariate_timeseries[TIMESERIES_KEYS.IDENTIFIERS][identifiers_column]]

        item_metrics[METRICS_DATASET.TARGET_COLUMN] = target_columns
        agg_metrics[METRICS_DATASET.TARGET_COLUMN] = METRICS_DATASET.AGGREGATED_ROW
        agg_metrics[METRICS_DATASET.TRAINING_TIME] = round(self.evaluation_time, 2)

        for identifiers_column in identifiers_columns:
            item_metrics[identifiers_column] = identifiers_values[identifiers_column]
            agg_metrics[identifiers_column] = METRICS_DATASET.AGGREGATED_ROW  # or keep empty but will cast integer to float

        metrics = item_metrics.append(agg_metrics, ignore_index=True)

        metrics = metrics[
            [METRICS_DATASET.TARGET_COLUMN]
            + identifiers_columns
            + [METRICS_DATASET.MODEL_COLUMN]
            + list(EVALUATION_METRICS_DESCRIPTIONS.keys())
            + [METRICS_DATASET.TRAINING_TIME]
        ]
        metrics[METRICS_DATASET.MODEL_PARAMETERS] = self._get_model_parameters_json(train_list_dataset)

        return metrics, identifiers_columns

    def _train_estimator(self, train_list_dataset):
        """Train a gluonTS estimator to get a predictor for models that can be trained
        or directly get the existing gluonTS predictor (e.g. for models that don't need training like trivial.identity)

        Args:
            train_list_dataset (gluonts.dataset.common.ListDataset): ListDataset created with the GluonDataset class.

        Returns:
            gluonts.model.predictor.Predictor
        """
        kwargs = {"freq": self.frequency, "prediction_length": self.prediction_length}
        if self.estimator is None:
            if ModelHandler.needs_num_samples(self):
                kwargs.update({"num_samples": 100})
            if self.context_length is not None and ModelHandler.can_use_context_length(self):
                kwargs.update({"context_length": self.context_length})
            predictor = ModelHandler.predictor(self, **kwargs)
        else:
            try:
                predictor = self.estimator.train(train_list_dataset)
            except Exception as err:
                raise ModelTrainingError(f"GluonTS '{self.model_name}' model crashed during training. Full error: {err}")
        return predictor

    def _get_model_parameters_json(self, train_list_dataset):
        """ Returns a JSON string containing model parameters and results """
        timeseries_number = len(train_list_dataset.list_data)
        timeseries_total_length = sum([len(ts[TIMESERIES_KEYS.TARGET]) for ts in train_list_dataset.list_data])
        return json.dumps(
            {
                "model_name": ModelHandler.get_label(self),
                "frequency": self.frequency,
                "prediction_length": self.prediction_length,
                "context_length": self.context_length,
                "epoch": self.epoch,
                "use_external_features": self.using_external_features,
                "use_feat_static_cat": self.using_feat_static_cat,
                "batch_size": self.batch_size,
                "num_batches_per_epoch": self.num_batches_per_epoch,
                "timeseries_number": timeseries_number,
                "timeseries_average_length": round(timeseries_total_length / timeseries_number),
                "model_parameters": self.model_parameters,
            }
        )

    def _compute_mean_forecasts_timeseries(self, forecasts_list, train_list_dataset):
        """Compute mean forecasts timeseries for each Forecast of forecasts_list.

        Args:
            forecasts_list (list): List of gluonts.model.forecast.Forecast (objects storing the predicted distributions as samples).
            train_list_dataset (gluonts.dataset.common.ListDataset): ListDataset created with the GluonDataset class.

        Returns:
            Dictionary of list of forecasts timeseries (value) by identifiers (key). Key is None if no identifiers.
        """
        mean_forecasts_timeseries = {}
        for i, sample_forecasts in enumerate(forecasts_list):
            series = sample_forecasts.quantile_ts(0.5).rename(f"{self.model_name}_{train_list_dataset.list_data[i][TIMESERIES_KEYS.TARGET_NAME]}")
            if TIMESERIES_KEYS.IDENTIFIERS in train_list_dataset.list_data[i]:
                timeseries_identifier_key = tuple(sorted(train_list_dataset.list_data[i][TIMESERIES_KEYS.IDENTIFIERS].items()))
            else:
                timeseries_identifier_key = None

            if timeseries_identifier_key in mean_forecasts_timeseries:
                mean_forecasts_timeseries[timeseries_identifier_key] += [series]
            else:
                mean_forecasts_timeseries[timeseries_identifier_key] = [series]
        return mean_forecasts_timeseries
