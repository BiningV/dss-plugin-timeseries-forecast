# -*- coding: utf-8 -*-
import pandas as pd
import dataiku
from dataiku.customrecipe import get_recipe_config
from datetime import datetime
from plugin_io_utils import get_models_parameters, save_dataset
from dku_timeseries.global_models import GlobalModels
from plugin_config_loading import load_training_config

config = get_recipe_config()

global_params = load_training_config(config)
version_name = datetime.now().strftime('%Y-%m-%dT%H-%M-%S-%f')[:-3]

models_parameters = get_models_parameters(config)
print("ALX:models_parameters={}".format(models_parameters))
# TODO save with compression
save_dataset(
    dataset_name=global_params['input_dataset_name'],
    time_column_name=global_params['time_column_name'],
    target_columns_names=global_params['target_columns_names'],
    external_feature_columns=global_params['external_feature_columns'],
    model_folder=global_params['model_folder'],
    version_name=version_name
)

training_dataset = dataiku.Dataset(global_params['input_dataset_name'])
training_df = training_dataset.get_dataframe()

global_models = GlobalModels(
    target_columns_names=global_params['target_columns_names'],
    time_column_name=global_params['time_column_name'],
    frequency=global_params['frequency'],
    model_folder=global_params['model_folder'],
    epoch=global_params['epoch'],
    models_parameters=models_parameters,
    prediction_length=global_params['prediction_length'],
    training_df=training_df,
    make_forecasts=global_params['make_forecasts'],
    external_features_column_name=global_params['external_feature_columns']
)  # todo : integrate external features and multiple target columns
global_models.init_all_models()

df = global_models.evaluate_all(global_params['evaluation_strategy'])

global_models.fit_all()

global_params['evaluation_dataset'].write_with_schema(df)


global_models.save_all(version_name=version_name)

if global_params['make_forecasts']:
    forecasts_df = global_models.get_history_and_forecasts_df()
    global_params['evaluation_forecasts'].write_with_schema(forecasts_df)


# Naive estimator is in fact 3 models
# kwargs by default could be made visible in the interface (when in expert mode)
# Trainer has it's own set of kwargs. 2 kwargs in the interface or key prefix ?

"""
ketchup du 
models.rdata
contient tous les models entraines et les données d'entrainement (archivage), parametres d'entrainement

2eme recipe 
normalement, output vide

python: 
interogation du model : même horizon qu'a l'entrainement pour la version python (!= que R)
"""

"""
objet instancié par model, avec fonction create json
model sauvé par repertoire 
"""