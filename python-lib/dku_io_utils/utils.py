import re
import io
import os
import dill as pickle
from constants import AVAILABLE_MODELS
import pandas as pd
import json
import gzip
import logging


def read_from_folder(folder, path, obj_type):
    logging.info("Timeseries forecast - Loading {}".format(os.path.join(folder.get_path(), path)))
    if not folder.get_path_details(path=path)["exists"]:
        raise ValueError(
            "File at path {} doesn't exist in folder {}".format(path, folder.get_info()["name"])
        )
    with folder.get_download_stream(path) as stream:
        if obj_type == "pickle":
            return pickle.loads(stream.read())
        if obj_type == "pickle.gz":
            with gzip.GzipFile(fileobj=stream) as fgzip:
                return pickle.loads(fgzip.read())
        elif obj_type == "csv":
            data = io.StringIO(stream.read().decode())
            return pd.read_csv(data)
        elif obj_type == "csv.gz":
            with gzip.GzipFile(fileobj=stream) as fgzip:
                return pd.read_csv(fgzip)
        else:
            raise ValueError(
                "Can only read objects of type ['pickle', 'pickle.gz', 'csv', 'csv.gz'] from folder, not '{}'".format(
                    obj_type
                )
            )


def write_to_folder(obj, folder, path, obj_type):
    logging.info("Timeseries forecast - Saving {}".format(os.path.join(folder.get_path(), path)))
    with folder.get_writer(path) as writer:
        if obj_type == "pickle":
            writeable = pickle.dumps(obj)
            writer.write(writeable)
        elif obj_type == "pickle.gz":
            writeable = pickle.dumps(obj)
            with gzip.GzipFile(fileobj=writer, mode="wb", compresslevel=9) as fgzip:
                fgzip.write(writeable)
        elif obj_type == "json":
            writeable = json.dumps(obj).encode()
            writer.write(writeable)
        elif obj_type == "csv":
            writeable = obj.to_csv(sep=",", na_rep="", header=True, index=False).encode()
            writer.write(writeable)
        elif obj_type == "csv.gz":
            with gzip.GzipFile(fileobj=writer, mode="wb") as fgzip:
                fgzip.write(obj.to_csv(index=False).encode())
        else:
            raise ValueError(
                "Can only write objects of type ['pickle', 'pickle.gz', 'json', 'csv', 'csv.gz'] to folder, not '{}'".format(
                    obj_type
                )
            )


def get_models_parameters(config):
    models_parameters = {}
    for model in AVAILABLE_MODELS:
        if is_activated(config, model):
            model_presets = get_model_presets(config, model)
            if "prediction_length" in model_presets.get("kwargs", {}):
                raise ValueError("The value for 'prediction_length' cannot be changed")
            models_parameters.update({model: model_presets})
    return models_parameters


def is_activated(config, model):
    return config.get("{}_model_activated".format(model), False)


def get_model_kwargs(config, model):
    return config.get("{}_model_kwargs".format(model))


def get_model_presets(config, model):
    model_presets = {}
    matching_key = "{}_model_(.*)".format(model)
    for key in config:
        key_search = re.match(matching_key, key, re.IGNORECASE)
        if key_search:
            key_type = key_search.group(1)
            model_presets.update({key_type: config[key]})
    return model_presets


def set_column_description(output_dataset, column_description_dict, input_dataset=None):
    """Set column descriptions of the output dataset based on a dictionary of column descriptions

    Retains the column descriptions from the input dataset if the column name matches.

    Args:
        output_dataset: Output dataiku.Dataset instance
        column_description_dict: Dictionary holding column descriptions (value) by column name (key)
        input_dataset: Optional input dataiku.Dataset instance
            in case you want to retain input column descriptions
    """
    output_dataset_schema = output_dataset.read_schema()
    input_dataset_schema = []
    input_columns_names = []
    if input_dataset is not None:
        input_dataset_schema = input_dataset.read_schema()
        input_columns_names = [col["name"] for col in input_dataset_schema]
    for output_col_info in output_dataset_schema:
        output_col_name = output_col_info.get("name", "")
        output_col_info["comment"] = column_description_dict.get(output_col_name)
        if output_col_name in input_columns_names:
            matched_comment = [
                input_col_info.get("comment", "")
                for input_col_info in input_dataset_schema
                if input_col_info.get("name") == output_col_name
            ]
            if len(matched_comment) != 0:
                output_col_info["comment"] = matched_comment[0]
    output_dataset.write_schema(output_dataset_schema)
