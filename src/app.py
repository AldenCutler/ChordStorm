import urllib.parse
from datetime import datetime
from flask import Flask, redirect, request, jsonify, session, url_for, render_template
import requests
from openai import OpenAI
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
import time
import openmeteo_requests
from retry_requests import retry
import requests_cache
import pgeocode
import pandas as pd
import math
import re
import os

app = Flask(__name__)

topSongs = ""

REDIRECT_URI = 'http://localhost:5000/callback'

"""KEYS SETUP"""

# These are environment variables, you will need your own keys to test this code
# Specifically, you will need a Spotify Client ID and Client Secret, and an OpenAI API Key besides the Flask Secret Key
# On Windows, you can set the environment variables by running the following commands in the command prompt:
# setx TUNECAST_SPOTIFY_CLIENT_ID "your_client_id"
# setx TUNECAST_SPOTIFY_CLIENT_SECRET "your_client_secret"
# setx TUNECAST_OPENAI_API_KEY "your_api_key"
# setx TUNECAST_FLASK_SECRET_KEY "your_secret_key"

CLIENT_ID = os.environ["TUNECAST_SPOTIFY_CLIENT_ID"]
CLIENT_SECRET = os.environ["TUNECAST_SPOTIFY_CLIENT_SECRET"]

client = OpenAI(api_key=os.environ["TUNECAST_OPENAI_API_KEY"])

app.secret_key = os.environ["TUNECAST_FLASK_SECRET_KEY"]

"""MISC. SPOTIFY URLS"""

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'

@app.route('/')
def index():
    spotify_status = "Connect to Spotify to get started!"
    return render_template('index.html', spotify_status = spotify_status)

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/login')
def login():
    scope = scope = 'user-read-private user-read-email user-top-read user-follow-modify user-follow-read'

    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': REDIRECT_URI,
        'show-dialog': True
    }

    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    return redirect(auth_url)


@app.route('/callback')
def callback():
    if 'error' in request.args:
        return jsonify({"error": request.args['error']})

    if 'code' in request.args:
        req_body = {
            'code': request.args['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }

        response = requests.post(TOKEN_URL, data=req_body)
        token_info = response.json()

        session['access_token'] = token_info['access_token']
        session['refresh_token'] = token_info['refresh_token']
        session['expires_at'] = datetime.now().timestamp() + token_info['expires_in']

        return redirect('/topTracks')

@app.route('/topTracks')
def get_topTracks():
    if 'access_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    
    params = {
        'limit': 50,
        'time_range': 'short_term'
    }

    try:
        response = requests.get(API_BASE_URL + 'me/top/tracks', params=params, headers=headers)
        response.raise_for_status()  # Check for HTTP errors

        parsed_response_list, parsed_response_concatenated = extract_all_songs_as_string(response.json())
        
        print(parsed_response_list)
        
        global topSongs
        topSongs = parsed_response_concatenated
        
        spotify_status = "Spotify is connected!"

        return render_template('index.html', spotify_status = spotify_status)

    except requests.exceptions.RequestException as e:
        # Print the actual error message returned by the Spotify API
        print(f"Error fetching top tracks: {e}")
        return jsonify({"error": f"Failed to fetch top tracks. Spotify API error: {e}"})
    
def extract_all_songs_as_string(data):
    
    song_artist_list = []
    combined_string = ""

    # Check if 'items' key exists and has data
    if 'items' in data and data['items']:
        for item in data['items']:
            song_name = item.get('name', 'Unknown Song')
            artist_names = [artist['name'] for artist in item.get('artists', []) if 'name' in artist]

            # Combine song name with artist names using a pipe separator and add to the combined string
            song_artist = f"{song_name} | {', '.join(artist_names)}"
            song_artist_list.append(song_artist)
            combined_string += song_artist + "\n"

    return song_artist_list, combined_string.strip()
    

@app.route('/refresh-token')
def refresh_token():
    if 'refresh_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        req_body = {
            'grant_type': 'refresh_token',
            'refresh_token': session['refresh_token'],
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }

        response = requests.post(TOKEN_URL, data=req_body)
        new_token_info = response.json()

        session['access_token'] = new_token_info['access_token']
        session['expires_at'] = datetime.now().timestamp() + new_token_info['expires_in']

        return redirect('/topTracks')

@app.route('/get_recommendations')
def get_recommendations():
    # Get Zip Code from URL
    zip = request.args.get('zip')
    
    # if user goes to /display without a zip code, redirect to the index page
    if zip == None:
        return redirect(url_for('index'))
    # if no zip code is entered, return to the index page
    # type(zip) is <str>, so len(zip) can check this
    if len(zip) == 0:
        return redirect(url_for('index'))
    # check if the zip code is a number 
    # 501 is the lowest zip code in the US, for an IRS office in Holtsville, NY.
    # 99950 is the highest, belonging to Ketchikan, AK.
    if not zip.isnumeric() or int(zip) > 99950 or int(zip) < 501:
        return redirect(url_for('index'))
    
        
    place_data = get_place_data(zip)
    lat = place_data['latitude']
    lon = place_data['longitude']
    print(lat, lon)
    weather_data = {}
    sky = ""
    icon = ""
    try:
        weather_data = get_weather(lat, lon)
        # Icon Codes for the weather icons from fonts.google.com/icons
        icon_codes = {
            0: 'clear_day' if weather_data['current']['is_day'] else 'clear_night',
            1: 'clear_day' if weather_data['current']['is_day'] else 'clear_night',
            2: 'partly_cloudy_day' if weather_data['current']['is_day'] else 'partly_cloudy_night',
            3: 'partly_cloudy_day' if weather_data['current']['is_day'] else 'partly_cloudy_night',
            45: 'foggy',
            48: 'foggy',
            51: 'rainy',
            53: 'rainy',
            55: 'rainy',
            56: 'rainy',
            57: 'rainy',
            61: 'rainy',
            63: 'rainy',
            65: 'rainy',
            66: 'rainy',
            67: 'rainy',
            71: 'weather_snowy',
            73: 'weather_snowy',
            75: 'weather_snowy',
            77: 'weather_snowy',
            80: 'rainy',
            81: 'rainy',
            82: 'rainy',
            85: 'weather_snowy',
            86: 'weather_snowy',
            95: 'thunderstorm',
            96: 'thunderstorm',
            99: 'thunderstorm',
        }
        # Sky Codes for the weather descriptions
        sky_codes = {
            0: 'Clear',
            1: 'Mainly Clear',
            2: 'Partly Cloudy',
            3: 'Overcast',
            45: 'Fog',
            48: 'Freezing Fog',
            51: 'Light Drizzle',
            53: 'Drizzle',
            55: 'Heavy Drizzle',
            56: 'Light Freezing Drizzle',
            57: 'Freezing Drizzle',
            61: 'Light Rain',
            63: 'Rain',
            65: 'Heavy Rain',
            66: 'Light Freezing Rain',
            67: 'Freezing Rain',
            71: 'Light Snow',
            73: 'Snow',
            75: 'Heavy Snow',
            77: 'Snow Grains',
            80: 'Light Showers',
            81: 'Showers',
            82: 'Heavy Showers',
            85: 'Light Snow Showers',
            86: 'Snow Showers',
            95: 'Thunderstorm',
            96: 'Thunderstorm with Light Hail',
            99: 'Thunderstorm with Hail',
    }           
    
        sky = sky_codes[weather_data['current']['weather_code']]
        icon = icon_codes[weather_data['current']['weather_code']]
    except TypeError:
        redirect(url_for('index'))
    
    
    user_top_tracks = topSongs
    weather = sky
    
    thread = client.beta.threads.create()

    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="Current weather is " + weather + ". The user's top 50 latest songs are, in format Songname | Artist1, Artist2,...: " + topSongs
    )

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id="asst_pwk8lo9P7abyLiOpdWb1dpAw"
    )

    run = client.beta.threads.runs.retrieve(
        thread_id = thread.id,
        run_id = run.id
    )
    
    time.sleep(20)

    messages = client.beta.threads.messages.list(
        thread_id = thread.id
    )

    parsed_messages = []

    for message in reversed(messages.data):
        print(message.role + ": " + message.content[0].text.value)
        parsed_messages.append(message.content[0].text.value)
        
    print("I got to point 1, the len of messages is " + str(len(parsed_messages)))
    
    assistant_output = parsed_messages[len(parsed_messages) - 1]
    
    print("I got to point 2, this is the assistant output: " + assistant_output)
    
    paragraph, song_links = process_assistant_output(assistant_output)
        
    print("I got to point 3" + paragraph + str(song_links))
        
    return render_template('main.html', weather_data = weather_data, place_data = place_data, sky = sky, icon = icon, paragraph=paragraph, song_links=song_links)


def process_assistant_output(assistant_output):
    paragraph_pattern = r"^(.*?)The 5 songs for your tunecast are:"
    paragraph_match = re.search(paragraph_pattern, assistant_output, re.DOTALL)
    paragraph = paragraph_match.group(1).strip() if paragraph_match else ""

    song_pattern = r'"(.*?)" by (.*?)(?=$|\n)'
    songs = re.findall(song_pattern, assistant_output)

    client_credentials_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    sp = Spotify(client_credentials_manager=client_credentials_manager)

    song_links = []

    for song, artists in songs:
        query = f'track:{song} artist:{artists}'
        results = sp.search(q=query, type='track', limit=1)

        tracks = results.get('tracks', {}).get('items', [])
        if tracks:
            track_id = tracks[0].get('id')
            embed_link = f"https://open.spotify.com/embed/track/{track_id}"
            song_links.append(embed_link)

    return paragraph, song_links



def get_place_data(zip):
    nomi = pgeocode.Nominatim('us')
    return nomi.query_postal_code(zip)

### For more information/docs: https://pypi.org/project/pgeocode/
# This package "pgeocode" is used to get the latitude and longitude of a zip code
# It currently supports 83 countries, but without a way to get the country code from the zip code, 
# it would be significantly more complicated to use for countries other than the US.
# @app.route('/display')
def get_weather(lat, lon):
    
    if math.isnan(lat) or math.isnan(lon):
        return redirect(url_for('index'))
    
    if lat > 90 or lat < -90 or lon > 180 or lon < -180:
        # return render_template('invalid.html')
        return redirect(url_for('index'))
    
    # if the zip code is not a number,
    # meaning pgeocode was unable to find the zip code in the US,
    # show invalid zip code error
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        # return render_template('invalid.html')
        return redirect(url_for('index'))
    
    # get the weather data
    weather_data = get_weather_data(lat, lon)
    print(weather_data)
    
    # render the weather template with the weather data
    # return render_template('main.html', weather_data = weather_data, data = place_data, sky = sky, icon = icon)
    return weather_data


def get_weather_data(lat, lon):
    
    # Setup the Open-Meteo API client with cache and retry on error
    cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    openmeteo = openmeteo_requests.Client(session = retry_session)

    # Make sure all required weather variables are listed here
    # The order of variables in hourly or daily is important to assign them correctly below
    API_URL = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ["temperature_2m", "is_day", "weather_code"],
        # "hourly": ["uv_index", "is_day"],
        "daily": ["temperature_2m_max", "temperature_2m_min"],
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
        "forecast_days": 3,
    }
    
    # Call the API
    responses = openmeteo.weather_api(API_URL, params=params)

    # Process first location. Add a for-loop for multiple locations or weather models
    response = responses[0]
    print(f"Coordinates {response.Latitude()}°E {response.Longitude()}°N")
    print(f"Elevation {response.Elevation()} m asl")
    print(f"Timezone {response.Timezone()} {response.TimezoneAbbreviation()}")
    print(f"Timezone difference to GMT+0 {response.UtcOffsetSeconds()} s")

    # Current values. The order of variables needs to be the same as requested.
    # Current data updates every 15 minutes. Time zone is in GMT+0, so it needs to be converted to local time. 
    # You can use response.UtcOffsetSeconds() to get the offset in seconds. 
    current = response.Current()
    time = current.Time() + response.UtcOffsetSeconds()
    current_data = {
        "date": pd.to_datetime(time, unit = "s"),
        "temperature_2m": current.Variables(0).Value(),
        "is_day": current.Variables(1).Value(),
        "weather_code": current.Variables(2).Value(),
    }
    
    # Process daily data. The order of variables needs to be the same as requested.
    daily = response.Daily()
    daily_temperature_2m_max = daily.Variables(0).ValuesAsNumpy()
    daily_temperature_2m_min = daily.Variables(1).ValuesAsNumpy()

    daily_data = {"date": pd.date_range(
        start = pd.to_datetime(daily.Time(), unit = "s"),
        end = pd.to_datetime(daily.TimeEnd(), unit = "s"),
        freq = pd.Timedelta(seconds = daily.Interval()),
        inclusive = "left"
    )}
    daily_data["temperature_2m_max"] = daily_temperature_2m_max
    daily_data["temperature_2m_min"] = daily_temperature_2m_min
    
    data = {
        'daily': daily_data,
        'current': current_data
    }
    
    return data



if __name__ == '__main__':
    app.run(debug=True)