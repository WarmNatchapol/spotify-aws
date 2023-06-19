# import libraries
import os
import base64
import requests
import json
import boto3
from datetime import datetime
import dateutil.tz


# define config class
class Config:
    # get client_id and client_secret from environment variables
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")
    # get raw data bucket name from environment variables
    raw_data_bucket = os.environ.get("RAW_DATA_BUCKET")
    # get slack incoming webhook url from environment variables
    slack_url = os.environ.get("SLACK_URL")
    
    # thai timezone
    thai_tz = dateutil.tz.gettz("Asia/Bangkok")
    # current datetime
    current_datetime = datetime.now(thai_tz).strftime("%Y%m%d_%H%M%S")


# define send slack notification function
# docs - https://api.slack.com/messaging/webhooks
def slack_notification(text):
    # convert text dictionary to json
    data = json.dumps({"text": text})
    # headers
    headers = {"Content-Type": "application/json"}
    # post message to slack
    requests.post(Config.slack_url, data=data, headers=headers)


# define get authorization token function
# docs - https://developer.spotify.com/documentation/web-api/tutorials/client-credentials-flow
def get_auth():
    # prepare authorization string
    auth_str = f"{Config.client_id}:{Config.client_secret}"
    # encode to bytes
    auth_bytes = auth_str.encode("utf-8")
    # encode to base64
    auth_base64 = base64.b64encode(auth_bytes).decode()

    # api url
    url = "https://accounts.spotify.com/api/token"
    # authorization options
    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    form = {"grant_type": "client_credentials"}

    # post authorization request
    response = requests.post(url=url, headers=headers, data=form)

    # if response code = 200
    if response.status_code == 200:
        # extract access token from response
        token = response.json()["access_token"]
        return token
    # else
    else:
        # send slack notification
        text = f"There is an error in get authorization token from Spotify, {response.status_code}"
        slack_notification(text)


# define get playlist data from spotify api function
# docs - https://developer.spotify.com/documentation/web-api/reference/get-playlist
def get_playlist(token, playlist_id):
    # api url
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
    # headers
    headers = {"Authorization": f"Bearer {token}"}

    # get response
    response = requests.get(url=url, headers=headers)

    # if response code = 200
    if response.status_code == 200:
        # convert to dictionary
        result = response.json()
        return result
    # else
    else:
        # send slack notification
        text = f"There is an error in get playlist data from Spotify, {response.status_code}"
        slack_notification(text)


# upload raw data to s3
# docs - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_object.html
def upload_to_s3(raw_data):
    # processing foler and raw data filename
    filename = f"processing/{Config.current_datetime}.json"
    
    # s3 client
    client = boto3.client("s3")
    # put raw data to raw data bucket
    client.put_object(
        Body = json.dumps(raw_data),
        Bucket = Config.raw_data_bucket,
        Key = filename
        )


# define lambda entry function
def lambda_handler(event, context):
    # try
    try:
        # get access token
        token = get_auth()
        # get raw data playlist
        raw_data = get_playlist(token, playlist_id="37i9dQZEVXbMnz8KIWsvf9")
        # upload raw data to raw data bucket in s3
        upload_to_s3(raw_data=raw_data)

        # send slack notification
        text = "Extracted data from Spotify API and loaded to S3 successfully"
        slack_notification(text)
    # except
    except:
        # send slack notification
        slack_notification("THERE IS AN ERROR WITH EXTRACT DATA FROM SPOTIFY API!!")
    
    # return response to logs
    return {
        "statusCode": 200,
        "body": json.dumps("Extracted data from Spotify API and loaded to S3 successfully")
    }