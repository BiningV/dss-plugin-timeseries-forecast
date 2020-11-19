# -*- coding: utf-8 -*-
import re
import dataiku
from constants import MODEL_LABELS, TIMESTAMP_REGEX_PATTERN


def do(payload, config, plugin_config, inputs):
    """
    retrieve a list of models from the summary.csv file of the S3 Input Folder
    """
    choices = []

    input_folder_name = [input["fullName"] for input in inputs if input["type"] == "MANAGED_FOLDER"][0]

    input_folder = dataiku.Folder(input_folder_name)

    sessions = []
    for child in input_folder.get_path_details(path="/")["children"]:
        if re.match(TIMESTAMP_REGEX_PATTERN, child["name"]):
            sessions += [child["name"]]

    if payload.get("parameterName") == "manually_selected_session":
        for session in sorted(sessions):
            choices += [{"label": session, "value": session}]

    elif payload.get("parameterName") == "manually_selected_model_label":
        model_labels = set()
        for session in sessions:
            for child in input_folder.get_path_details(path="/{}".format(session))["children"]:
                if child["directory"] and child["name"] in MODEL_LABELS.values():
                    model_labels.add(child["name"])

        for model in model_labels:
            choices += [{"label": model, "value": model}]

    elif payload.get("parameterName") == "model_selection_mode":
        choices = [{"label": "Automatic", "value": "auto"}]
        if len(sessions) > 0:
            choices += [{"label": "Manual", "value": "manual"}]

    return {"choices": choices}
