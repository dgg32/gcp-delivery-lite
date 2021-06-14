import os
import itertools
import json
import requests
import numpy as np

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

KEY = os.environ.get('KEY')
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
SENDER = os.environ.get('SENDER')

def driving_time_and_distance(ori, dest):
    """get the dict of distance between two places
    
    Args:
        ori (str): Place A
        dest (str): Place B

    
    Returns:
        dict: return a dict of distance description
    """

    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?key={KEY}&origins={ori}&destinations={dest}&mode=driving&language=en-EN&sensor=false"
    result= json.loads(requests.get(url).text)


    return {"distance_value": result["rows"][0]["elements"][0]["distance"]["value"], "distance_text": result["rows"][0]["elements"][0]["distance"]["text"], "duration_text": result["rows"][0]["elements"][0]["duration"]["text"], "duration_value": result["rows"][0]["elements"][0]["duration"]["value"]}

def distance_matrix_gcp(destinations):
    """get the pairwise distance matrix with gcp
    
    Args:
        df (pd.Dataframe): a dataframe with a column "address"

    
    Returns:
        dict: return a dict of distance description
    """


    indice = range(len(destinations))

    dis_max = np.zeros(shape=(len(destinations),len(destinations)))

    for pair in itertools.combinations(indice, 2):
        dis = driving_time_and_distance(destinations[pair[0]]["address"], destinations[pair[1]]["address"])['distance_value']

        
        dis_max[pair[0]][pair[1]] = dis
        dis_max[pair[1]][pair[0]] = dis


    return {"distance_matrix": dis_max.tolist()}


def send_email (dest_mail, subject, text):
    """Send email to carriers
    
    Args:
        dest_mail (str): target email
        subject (str): email subject
        text (str): email content

    
    Returns:
    """
    message = Mail(

    from_email=SENDER,

    to_emails=dest_mail,

    subject=subject,

    html_content=text)

    try:

        sg = SendGridAPIClient(f"{SENDGRID_API_KEY}")

        response = sg.send(message)

        print(response.status_code)

        print(response.body)

        print(response.headers)

    except Exception as e:

        print(e.message)