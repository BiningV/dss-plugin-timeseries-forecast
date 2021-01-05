from gluonts.model.estimator import Estimator
from gluonts.model.forecast import SampleForecast
from gluonts.model.predictor import RepresentablePredictor
from gluonts.support.pandas import frequency_add
from gluonts.core.component import validated
from gluonts.time_feature import get_seasonality
from custom_gluon_models.utils import cast_kwargs
from constants import TIMESERIES_KEYS
import pmdarima as pm
import numpy as np
from safe_logger import SafeLogger
from tqdm import tqdm


logger = SafeLogger("Forecast plugin - ARIMA")


class ArimaPredictor(RepresentablePredictor):
    """
    An abstract predictor that can be subclassed by models that are not based
    on Gluon. Subclasses should have @validated() constructors.
    (De)serialization and value equality are all implemented on top of the
    @validated() logic.

    Parameters
    ----------
    prediction_length
        Prediction horizon.
    freq
        Frequency of the predicted data.
    """

    # TODO implement custom serializer

    @validated()
    def __init__(self, prediction_length, freq, trained_models, lead_time=0):
        super().__init__(freq=freq, lead_time=lead_time, prediction_length=prediction_length)
        self.trained_models = trained_models

    def predict(self, dataset, **kwargs):
        """

        Args:
            dataset (gluonts.dataset.common.Dataset): Dataset after wich to predict forecasts.

        Yields:
            SampleForecast of predictions.
        """
        logger.info("Prediction timeseries ...")
        for i, item in tqdm(enumerate(dataset)):
            yield self.predict_item(item, self.trained_models[i])

    def predict_item(self, item, trained_model):
        """Compute quantiles using the confidence intervals of auto_arima.

        Args:
            item (DataEntry): One timeseries.
            trained_model (list): List of trained auto_arima models.

        Returns:
            SampleForecast of quantiles.
        """
        start_date = frequency_add(item["start"], len(item["target"]))

        prediction_external_features = self._set_prediction_external_features(item)

        samples = []
        for alpha in np.arange(0.02, 1.01, 0.02):
            confidence_intervals = trained_model.predict(n_periods=self.prediction_length, X=prediction_external_features, return_conf_int=True, alpha=alpha)[1]
            samples += [confidence_intervals[:, 0], confidence_intervals[:, 1]]

        return SampleForecast(samples=np.stack(samples), start_date=start_date, freq=self.freq)

    def _set_prediction_external_features(self, item):
        prediction_external_features = None
        if TIMESERIES_KEYS.FEAT_DYNAMIC_REAL_COLUMNS_NAMES in item:
            prediction_external_features = item[TIMESERIES_KEYS.FEAT_DYNAMIC_REAL][:, -self.prediction_length :].T
        return prediction_external_features


class ArimaEstimator(Estimator):
    @validated()
    def __init__(self, prediction_length, freq, use_feat_dynamic_real=False, **kwargs):
        super().__init__()
        self.prediction_length = prediction_length
        self.freq = freq
        self.use_feat_dynamic_real = use_feat_dynamic_real
        self.kwargs = cast_kwargs(kwargs)

    def train(self, training_data, validation_data=None):
        """Train the estimator on the given data.

        Args:
            training_data (gluonts.dataset.common.Dataset): Dataset to train the model on.
            validation_data (gluonts.dataset.common.Dataset, optional): Dataset to validate the model on during training. Defaults to None.

        Returns:
            Predictor containing the trained model.
        """
        trained_models = []
        logger.info("Training one model per timeseries ...")
        for item in tqdm(training_data):
            external_features = self._set_external_features(self.kwargs, item)
            model = pm.auto_arima(item["target"], X=external_features, trace=False, **self.kwargs)
            trained_models += [model]

        return ArimaPredictor(prediction_length=self.prediction_length, freq=self.freq, trained_models=trained_models)

    def _set_external_features(self, kwargs, item):
        external_features = None
        if self.use_feat_dynamic_real:
            external_features = item[TIMESERIES_KEYS.FEAT_DYNAMIC_REAL].T
            logger.info("Using external features")
        return external_features
