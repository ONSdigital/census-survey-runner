from app import settings
import json
import os


def load_schema(schema_id):
    """
    Given a schema id this method will load the correct schema file from disk. Currently the parameter is ignored
    and the MCI schema is returned
    :param schema_id: The id of the schema file
    :return: The Schema representing in a dict
    """
    schema_file = open(os.path.join(settings.EQ_SCHEMA_DIRECTORY, "mci.json"), encoding="utf8")
    return json.load(schema_file)