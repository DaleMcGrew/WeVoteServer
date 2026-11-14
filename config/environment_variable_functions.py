# config/environment_variable_functions.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

import json
import os

from django.core.exceptions import ImproperlyConfigured

# Load JSON-based environment_variables if available
json_environment_variables = {}
try:
    with open("config/environment_variables.json") as f:
        json_environment_variables = json.loads(f.read())
except Exception as e:
    pass
    # print "base.py: environment_variables.json missing"
    # Can't use logger in the settings file due to loading sequence


# ########## Logging configurations ###########
#   LOG_STREAM          Boolean     True will turn on stream handler and write to command line.
#   LOG_FILE            String      Path to file to write to. Make sure executing
#                                   user has permissions.
#   LOG_STREAM_LEVEL    Integer     Log level of stream handler: CRITICAL, ERROR, INFO, WARN, DEBUG
#   LOG_FILE_LEVEL      Integer     Log level of file handler: CRITICAL, ERROR, INFO, WARN, DEBUG
#   NOTE: These should be set in the environment_variables.json file
def convert_logging_level(log_level_text_descriptor):
    import logging
    # Assume error checking has been done and that the string is a valid logging level
    if log_level_text_descriptor == "CRITICAL":
        return logging.CRITICAL
    if log_level_text_descriptor == "ERROR":
        return logging.ERROR
    if log_level_text_descriptor == "INFO":
        return logging.INFO
    if log_level_text_descriptor == "WARN":
        return logging.WARN
    if log_level_text_descriptor == "DEBUG":
        return logging.DEBUG


def get_environment_variable(var_name, json_environment_vars=json_environment_variables, no_exception=False):
    """
    Get the environment variable or return exception. Don't return exception if no_exception is True
    """
    try:
        # Environment variables can be set with this for example: export GOOGLE_CIVIC_API_KEY=<API KEY HERE>
        val = os.environ[var_name]
        # handle boolean variables; return bool value when string is "true" or "false"
        try:
            if val.lower() == 'true':
                return True
            elif val.lower() == 'false':
                return False
        except Exception as e:
            pass
        return val
    except KeyError:
        pass

    if json_environment_vars:
        if var_name in json_environment_vars:
            val = json_environment_vars[var_name]
            # handle boolean variables; return bool value when string is "true" or "false"
            try:
                if val.lower() == 'true':
                    return True
                elif val.lower() == 'false':
                    return False
            except Exception as e:
                pass
            return val
        else:
            variable_not_found = True
    else:
        variable_not_found = True

    if variable_not_found:
        # Can't use logger in the settings file due to loading sequence
        error_message = "ERROR: Unable to set the {} variable from os.environ or JSON file".format(var_name)
        try:
            import logging
            logging.error(error_message)
        except Exception as e:
            pass
        if no_exception:
            return ''
        else:
            raise ImproperlyConfigured(error_message)
    else:
        return ''


def get_environment_variable_default(var_name, default_value):
    if var_name in json_environment_variables:
        return json_environment_variables[var_name]

    try:
        return os.environ[var_name]
    except KeyError:
        return default_value


def get_we_vote_server_root_url():
    if get_environment_variable_default("RUNNING_IN_DEVELOPER_MODE", False):
        protocol = get_environment_variable_default("WE_VOTE_SERVER_PROTOCOL", "https")
        domain = get_environment_variable_default("WE_VOTE_SERVER_DOMAIN_HTTP" if protocol == "http" else "WE_VOTE_SERVER_DOMAIN_HTTPS", "wevotedeveloper.com")
    else:
        protocol = get_environment_variable_default("WE_VOTE_SERVER_PROTOCOL", "http")
        domain = get_environment_variable_default("WE_VOTE_SERVER_DOMAIN_HTTP" if protocol == "http" else "WE_VOTE_SERVER_DOMAIN_HTTPS", "localhost")

    port = get_environment_variable_default("WE_VOTE_SERVER_PORT", "8000")
    if len(port):
        url = f"{protocol}://{domain}:{port}"
    else:
        url = f"{protocol}://{domain}"
    return url
