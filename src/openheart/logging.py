import json
import logging
import requests
import os

# Debug settings
oh_debug = os.environ.get("OH_DEBUG").lower() == 'true'

# For sending error logs to slack
class HTTPSlackHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        json_text = json.dumps({"text": log_entry})
        url = 'https://hooks.slack.com/services/<org_id>/<api_key>'
        return requests.post(url, json_text, headers={"Content-type": "application/json"}).content


log_dict_config = {
"version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s %(threadName)s [%(filename)s:%(lineno)s - %(funcName)s() ]: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        #"slack": {
        #    "class": "HTTPSlackHandler",
        #    "formatter": "default",
        #    "level": "ERROR",
        #},
        "log_file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "formatter": "default",
            "filename": os.environ.get("OH_DATA_PATH")+"/logs/oh_log.log",
            "when": "midnight",
            "backupCount": 10,
            "delay": "True",
        },
    },
    "root": {
        "level": "DEBUG" if oh_debug else "INFO",
        #"handlers": ["console"] if oh_debug else ["slack", "log_file"],
        "handlers": ["console"] if oh_debug else ["log_file",],
    }
}
