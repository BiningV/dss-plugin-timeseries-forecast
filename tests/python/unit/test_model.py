from gluonts_forecasts.model import Model
from gluonts_forecasts.gluon_dataset import GluonDataset
from gluonts_forecasts.model_handler import MODEL_DESCRIPTORS, LABEL
from constants import METRICS_DATASET, EVALUATION_METRICS_DESCRIPTIONS
from datetime import datetime
from pandas.api.types import is_datetime64_ns_dtype
import pandas as pd
import numpy as np
import pytest


class TestModel:
    def setup_class(self):
        self.df = pd.DataFrame(
            {
                "date": ["2018-01-06", "2018-01-07", "2018-01-08", "2018-01-06", "2018-01-07", "2018-01-08"],
                "volume": [2, 4, 2, 5, 2, 5],
                "revenue": [12, 13, 14, 15, 11, 10],
                "store": [1, 1, 1, 1, 1, 1],
                "item": [1, 1, 1, 2, 2, 2],
                "is_holiday": [0, 0, 0, 0, 1, 0],
                "is_weekend": [1, 0, 0, 1, 0, 0],
            }
        )
        self.df["date"] = pd.to_datetime(self.df["date"]).dt.tz_localize(tz=None)
        self.gluon_dataset = GluonDataset(
            dataframe=self.df,
            time_column_name="date",
            frequency="D",
            target_columns_names=["volume", "revenue"],
            timeseries_identifiers_names=["store", "item"],
            external_features_columns_names=["is_holiday", "is_weekend"],
            min_length=2,
        )
        self.prediction_length = 1
        gluon_list_datasets = self.gluon_dataset.create_list_datasets(cut_lengths=[self.prediction_length, 0])
        self.train_list_dataset = gluon_list_datasets[0]
        self.test_list_dataset = gluon_list_datasets[1]

    def test_deepar(self):
        model_name = "deepar"
        model = Model(
            model_name,
            model_parameters={"activated": True, "kwargs": {"dropout_rate": "0.3", "cell_type": "gru"}},
            frequency="D",
            prediction_length=self.prediction_length,
            epoch=1,
            use_external_features=True,
            batch_size=32,
            num_batches_per_epoch=50,
        )
        metrics, identifiers_columns, forecasts_df = model.train_evaluate(self.train_list_dataset, self.test_list_dataset, make_forecasts=True)

        TestModel.metrics_assertions(metrics, model_name)
        TestModel.forecasts_assertions(forecasts_df, model_name, prediction_length=self.prediction_length)

    def test_transformer(self):
        model_name = "transformer"
        model = Model(
            model_name,
            model_parameters={"activated": True, "kwargs": {"model_dim": 16}},
            frequency="D",
            prediction_length=self.prediction_length,
            epoch=1,
            use_external_features=True,
            batch_size=32,
            num_batches_per_epoch=50,
        )
        metrics, identifiers_columns, forecasts_df = model.train_evaluate(self.train_list_dataset, self.test_list_dataset, make_forecasts=True)

        TestModel.metrics_assertions(metrics, model_name)
        TestModel.forecasts_assertions(forecasts_df, model_name, prediction_length=self.prediction_length)

    def test_seasonal_naive(self):
        model_name = "seasonal_naive"
        model = Model(
            model_name,
            model_parameters={"activated": True, "kwargs": {}},
            frequency="D",
            prediction_length=self.prediction_length,
            epoch=1,
            use_external_features=False,
            batch_size=32,
            num_batches_per_epoch=50,
        )
        metrics, identifiers_columns, forecasts_df = model.train_evaluate(self.train_list_dataset, self.test_list_dataset, make_forecasts=True)

        TestModel.metrics_assertions(metrics, model_name)
        TestModel.forecasts_assertions(forecasts_df, model_name, prediction_length=self.prediction_length)

    def test_mqcnn(self):
        model_name = "mqcnn"
        model = Model(
            model_name,
            model_parameters={"activated": True, "kwargs": {}},
            frequency="D",
            prediction_length=self.prediction_length,
            epoch=1,
            use_external_features=False,
            batch_size=32,
            num_batches_per_epoch=50,
        )
        model.train(self.test_list_dataset)
        assert model.predictor is not None

    @staticmethod
    def metrics_assertions(metrics, model_name):
        expected_metrics_columns = ["store", "item"]
        expected_metrics_columns += [
            METRICS_DATASET.TARGET_COLUMN,
            METRICS_DATASET.MODEL_COLUMN,
            METRICS_DATASET.MODEL_PARAMETERS,
            METRICS_DATASET.TRAINING_TIME,
        ]
        expected_metrics_columns += list(EVALUATION_METRICS_DESCRIPTIONS.keys())
        assert len(metrics.index) == 5
        assert set(metrics.columns) == set(expected_metrics_columns)
        assert metrics[METRICS_DATASET.MODEL_COLUMN].unique() == MODEL_DESCRIPTORS[model_name][LABEL]

    @staticmethod
    def forecasts_assertions(forecasts_df, model_name, prediction_length=1):
        assert len(forecasts_df.index) == 2
        assert forecasts_df["index"].nunique() == prediction_length
