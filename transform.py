# import libraries
import os
from datetime import datetime
import dateutil.tz
import json
import requests
import boto3
import pandas as pd


# define config class
class Config:
    # get raw data and transformed data bucket name from environment variables
    raw_data_bucket = os.environ.get("RAW_DATA_BUCKET")
    transformed_data_bucket = os.environ.get("TRANSFORMED_DATA_BUCKET")
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


# define get raw data and filename from raw data bucket in s3 function
# docs - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/list_objects_v2.html
def get_filename_rawdata():
    # s3 client
    client = boto3.client("s3")
    # processing folder
    key = "processing/"
    
    # for loop to get filename and raw data
    for data in client.list_objects_v2(Bucket=Config.raw_data_bucket, Prefix=key)["Contents"]:
        # if filename end with json
        if data["Key"].split(".")[-1] == "json":
            # filename
            filename = data["Key"]
            # raw data
            response = client.get_object(Bucket=Config.raw_data_bucket, Key=filename)
            # convert to dictionary
            raw_data = json.loads(response["Body"].read())
            
            # return filename and raw data
            return filename, raw_data


# define extract album data from raw data function
def extract_album(data):
    # create empty album list
    album_list = []

    # for loop to extract data
    for album in data["tracks"]["items"]:
        # extract album data
        album_dict = {
            "album_id": album["track"]["album"]["id"],
            "album_name": album["track"]["album"]["name"],
            "release_date": album["track"]["album"]["release_date"],
            "total_tracks": album["track"]["album"]["total_tracks"]
        }
        # if extracted data not in list
        if album_dict not in album_list:
            # append to list
            album_list.append(album_dict)
    
    # return extracted album data list
    return album_list


# define extract artist data from raw data function
def extract_artist(data):
    # create empty artist list
    artist_list = []

    # for loop to extract data
    for artists in data["tracks"]["items"]:
        for artist in artists["track"]["artists"]:
            # extract artist data
            artist_dict = {
                "artist_id": artist["id"],
                "artist_name": artist["name"]
            }
            # if extracted data not in list
            if artist_dict not in artist_list:
                # append to list
                artist_list.append(artist_dict)
    
    # return extracted artist list
    return artist_list


# define convert milliseconds to minutes function
def milli_to_min(milliseconds):
    # return minutes
    return round(milliseconds / 60000, 2)


# define extract track data from raw data function
def extract_track(data):
    # create empty track list
    track_list = []

    # for loop to extract data
    for track in data["tracks"]["items"]:
        # extract track data
        track_dict = {
            "track_id": track["track"]["id"],
            "track_name": track["track"]["name"],
            "duration": milli_to_min(track["track"]["duration_ms"]),
            "popularity": track["track"]["popularity"],
            "album_id": track["track"]["album"]["id"],
            "artist_id": track["track"]["artists"][0]["id"]
        }
        # if extracted data not in list
        if track_dict not in track_list:
            # append to list
            track_list.append(track_dict)

    # return extracted track list
    return track_list


# define transform data function
def transform_data(raw_data):
    # extract album, artist, and track data
    album_data = extract_album(data=raw_data)
    artist_data = extract_artist(data=raw_data)
    track_data = extract_track(data=raw_data)

    # convert to dataframe
    album_df = pd.DataFrame(album_data)
    artist_df = pd.DataFrame(artist_data)
    track_df = pd.DataFrame(track_data)

    # return album, artist, and track dataframe
    return album_df, artist_df, track_df


# define load transformed data to transformed data bucket function
# docs - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_object.html
def load_transformed_data(album_df, artist_df, track_df):
    # s3 client
    client = boto3.client("s3")

    # album folder and filename
    album_filename = f"album/{Config.current_datetime}.csv"
    # put album data to transformed data bucket in s3
    client.put_object(
        Body = album_df.to_csv(index=False),
        Bucket = Config.transformed_data_bucket,
        Key = album_filename
    )

    # artist folder and filename
    artist_filename = f"artist/{Config.current_datetime}.csv"
    # put artist data to transformed data bucket in s3
    client.put_object(
        Body = artist_df.to_csv(index=False),
        Bucket = Config.transformed_data_bucket,
        Key = artist_filename
    )

    # track folder and filename
    track_filename = f"track/{Config.current_datetime}.csv"
    # put track data to transformed data bucket in s3
    client.put_object(
        Body = track_df.to_csv(index=False),
        Bucket = Config.transformed_data_bucket,
        Key = track_filename
    )


# define move raw data from processing folder to processed folder in raw data bucket function
# there is no function to move object, so I need to copy and delete it
# copy docs - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/copy_object.html
# delete docs - https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/delete_object.html
def move_raw_data(filename):
    # s3 client
    client = boto3.client("s3")
    
    # raw data filename
    raw_data_filename = filename.split("/")[-1]
    # processed folder and filename
    destination_key = f"processed/{raw_data_filename}"
    # copy source
    copy_source = {
        "Bucket": Config.raw_data_bucket,
        "Key": filename
    }
    
    # copy object from processing folder to processed folder in raw data bucket
    client.copy_object(CopySource=copy_source, Bucket=Config.raw_data_bucket, Key=destination_key)
    # delete raw data in processing folder in raw data bucket
    client.delete_object(Bucket=Config.raw_data_bucket, Key=filename)
    
    
# define lambda entry function
def lambda_handler(event, context):
    # try
    try:
        # get filename and raw data from raw data bucket
        filename, raw_data = get_filename_rawdata()
        # transform raw data to album, artist, and track dataframe
        album_df, artist_df, track_df = transform_data(raw_data)
        # load album, artist, and track data to transformed data bucket
        load_transformed_data(album_df, artist_df, track_df)
        # move raw data from processing folder to processed folder in raw data bucket
        move_raw_data(filename)
        # send slack notification
        slack_notification("Transformed and Loaded data to S3 successfully")
    # except
    except:
        # send slack notification
        slack_notification("THERE IS AN ERROR WITH TRANSFORM AND LOAD PART!!")
    
    # return response to logs
    return {
        "statusCode": 200,
        "body": json.dumps("Transformed and Loaded data to S3 successfully")
    }