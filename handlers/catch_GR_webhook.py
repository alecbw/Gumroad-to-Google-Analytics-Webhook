from utility.util import *

import os
from datetime import datetime, timedelta
from urllib.parse import parse_qs
import logging

import boto3
import requests

############################################################################################


def lambda_handler(event, context):
    param_dict, missing_params = validate_params(event,
        required_params=["Secret_Key"],
        optional_params=[]
    )
    logging.info(event)
    if param_dict.get("Secret_Key") not in [os.environ["SECRET_KEY"], "export SECRET_KEY=" + os.environ["SECRET_KEY"]]:
        return package_response(f"Please authenticate", 403, warn="please auth")

    # parse_qs writes every value as a list, so we subsequently unpack those lists
    webhook_data = parse_qs(event["body"])
    webhook_data = {k:v if len(v)>1 else v[0] for k,v in webhook_data.items()}

    timestamp = datetime.strptime(webhook_data.pop("sale_timestamp").replace("T", " ").replace("Z", ""), "%Y-%m-%d %H:%M:%S")
    timestamp = timestamp - timedelta(hours=7)

    data_to_write = {
        "email": webhook_data.pop("email"),
        "timestamp": int(timestamp.timestamp()),
        "value": int(webhook_data.pop("price")), # need to divide by 100 later fyi
        "offer_code": webhook_data.pop("offer_code", "No Code"),
        "country": webhook_data.pop("ip_country", "Unknown"),
        "refunded": 1 if webhook_data.pop("refunded") in ["true", "True", True] else 0,
        "data": webhook_data,
        "_ga": webhook_data.get("url_params[_ga]", ""),
        'updatedAt': int(datetime.now().timestamp()),
    }

    write_dynamodb_item(data_to_write, "GRWebhookData")

    track_google_analytics_event(test_dict)

    logging.info("Dynamo write and GA POST both appear to be successful")
    # return package_response(f"Dynamo write and GA POST both appear to be successful", 200)


############################################################################################

def track_google_analytics_event(data_to_write):
    tracking_url = "https://www.google-analytics.com/"
    if os.getenv("DEBUG") == True: tracking_url += "debug/"
    tracking_url += "collect?v=1&t=event"
    tracking_url += "&tid=" + "UA-131042255-2"
    tracking_url += "&ec=" + "product-" + ez_get(data_to_write, "data", "permalink") # event category
    tracking_url += "&ea=" + "purchased" # event action
    tracking_url += "&el=" + "purchased a product" # event label
    tracking_url += "&ev=" + str(ez_get(data_to_write, "value")) # value. stays as 100x higher bc no decimal for cents
    tracking_url += "&uid=" + ez_get(data_to_write, "_ga") # Anon Client ID (actually GA Session ID sent Cross-Domain)
    tracking_url += "&qt=" + str(int((datetime.now().timestamp() - data_to_write.get("timestamp")) * 1000)) # queue time - elapsed ms since event timestamp
    tracking_url += "&aip=1" # anonymize IP since it's always the server's IP
    tracking_url += "&ds=" + "python" # data source - identify that this is not the webserver itself

    # Not used in traditional event tracking
    # tracking_url += "&cu=" + ez_get(data, "data", "currency") # currency

    # Note: this will always return 200
    resp = requests.post(tracking_url)

# Note: this will BY DEFAULT overwrite items with the same primary key (upsert)
def write_dynamodb_item(dict_to_write, table, **kwargs):
    table = boto3.resource('dynamodb').Table(table)
    dict_to_write = {"Item": dict_to_write}

    try:
        table.put_item(**dict_to_write)
    except Exception as e:
        logging.error(e)
        logging.error(dict_to_write)
        return False

    if not kwargs.get("disable_print"): logging.info(f"Successfully did a Dynamo Write to {table}")


# times = "2020-09-12T21:37:48Z"
# timestamp = datetime.strptime(times.replace("T", " ").replace("Z", ""), "%Y-%m-%d %H:%M:%S")
# timestamp = timestamp - timedelta(hours=7)

# test_dict = {
#     "_ga": "2.197206063.1689275659.1599939181-845139552.1599939181",
#     "country": "Unknown",
#     "data": {"permalink": "WPLqz"},
#     "value": 19900,
#     "timestamp": timestamp,
# }