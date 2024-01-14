import urllib.parse
from datetime import datetime
from flask import Flask, redirect, request, jsonify, session, url_for, render_template
import requests
from openai import OpenAI
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
import time

app = Flask(__name__)

OPENWEATHER_API_KEY = ''

topSongs = ""

"""
Start of Spotify Setup
"""

app.secret_key = "fMyyn2dmoxkz9Vw0jlr34Xj67jNecPWj"

CLIENT_ID = '83ac151be94a4c38a29d022078b7d965'
CLIENT_SECRET = '31ec42c51a6f48428d65415e937d3d21'
REDIRECT_URI = 'http://localhost:5000/callback'

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'

"""
End of Spotify Setup
"""

"""
Start of GPT Assistant Setup
"""

client = OpenAI(api_key="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")

thread = client.beta.threads.create()

message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="It's rainy and I like the artist TWICE."
)

run = client.beta.threads.runs.create(
    thread_id=thread.id,
    assistant_id="asst_pwk8lo9P7abyLiOpdWb1dpAw"
)

run = client.beta.threads.runs.retrieve(
    thread_id = thread.id,
    run_id = run.id
)

messages = client.beta.threads.messages.list(
    thread_id = thread.id
)

for message in reversed(messages.data):
    print(message.role + ": " + message.content[0].text.value)

"""
End of GPT Assistant Setup
"""

# client_credentials_manager = SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET)
# sp = Spotify(client_credentials_manager=client_credentials_manager)

@app.route('/')
def index():
    text_to_display = "Welcome to Tunecast. <a href='/login'> Login with Spotify</a>"
    return render_template('index.html')

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

        return render_template('top_tracks.html', tracks = parsed_response_list)

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
    # data = request.json
    # zip_code = data.get('zip_code')
    
    weather = "rainy"

    # # Weather Data
    # weather_data = get_weather(zip_code)
    
    user_top_tracks = topSongs

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
        
    return render_template('recommendations.html', recommendations = parsed_messages)

def get_user_top_tracks():
    #abhi's stuff
    return "user's top tracks"

def get_weather(zip_code):
    #alden's stuff
    return "weather data"

def generate_recommendations(music_taste, weather_data):
    #ronit's stuff
    return "recommendations"

if __name__ == '__main__':
    app.run(debug=True)
