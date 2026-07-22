from flask import Flask, render_template, request, jsonify,redirect, url_for, session
import os
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass
import requests
import geopy.distance
import string
from geopy.geocoders import Nominatim
import folium
from datetime import datetime
import networkx as nx
from datetime import datetime
import winsound
from folium.plugins import HeatMap
from threading import Thread
import RiskTimer
import time
import heapq  # Import the heapq module
import json # Import the json module
from trie_sos import (
    create_sos_detector,
    detect_speech_and_alert,
    track_location,
    send_sos_alert,
    get_current_location,
    SOSWordDetector,
    is_sos_active
)

import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
MYSQL_DB = os.environ.get('MYSQL_DB', 'nari_suraksha')

def get_db_connection(use_db=True):
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        port=MYSQL_PORT,
        database=MYSQL_DB if use_db else None,
        charset='utf8mb4'
    )

def init_db():
    try:
        # First connect without specifying database to create it if not exists
        conn = get_db_connection(use_db=False)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB}")
        conn.commit()
        cursor.close()
        conn.close()

        # Connect to target database
        conn = get_db_connection(use_db=True)
        cursor = conn.cursor()
        
        # Check if users table exists and drop if it has 'gender' column
        try:
            cursor.execute("SHOW COLUMNS FROM users")
            columns = [row[0] for row in cursor.fetchall()]
            if 'gender' in columns:
                cursor.execute("DROP TABLE users")
                conn.commit()
        except Exception:
            pass

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                age INT NOT NULL
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")

init_db()

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Replace with your actual API key or service URL
IP_GEOLOCATION_API_URL = "https://api.ipgeolocation.io/ipgeo"
IP_GEOLOCATION_API_KEY = "abcdefg12345hijklmnop"

# Replace with your actual OpenRouteService API key
OPENROUTE_API_KEY = '5b3ce3597851110001cf6248fc9983571fcc4f99be09c0202832e14a'
OPENROUTE_BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"

# Fixed temporary starting location (Pune)
FIXED_START_LAT = 18.5204
FIXED_START_LON = 73.8567
FIXED_START_NAME = "Current Location (Pune)"

# --- Simulate a more detailed road network with distances and safety scores ---
graph_nodes = {
    "start": (18.5204, 73.8567),
    "A": (18.5225, 73.8540),
    "B": (18.5250, 73.8515),
    "C": (18.5280, 73.8500),
    "D": (18.5310, 73.8520),
    "E": (18.5350, 73.8550),
    "F": (18.5320, 73.8580),
    "G": (18.5290, 73.8600),
    "H": (18.5260, 73.8570),
    "end_node": (0, 0)  # Temporary end node
}

road_edges = [
    ("start", "A", {"distance_km": 0.5, "safety_score": 8}),
    ("A", "B", {"distance_km": 0.4, "safety_score": 7}),
    ("B", "C", {"distance_km": 0.6, "safety_score": 6}),
    ("C", "D", {"distance_km": 0.8, "safety_score": 7}),
    ("D", "E", {"distance_km": 0.5, "safety_score": 9}),
    ("E", "F", {"distance_km": 0.3, "safety_score": 8}),
    ("F", "G", {"distance_km": 0.7, "safety_score": 7}),
    ("G", "H", {"distance_km": 0.6, "safety_score": 8}),
    ("H", "B", {"distance_km": 0.4, "safety_score": 7}),
    ("A", "H", {"distance_km": 0.3, "safety_score": 9}),
    ("C", "H", {"distance_km": 0.5, "safety_score": 6}),
]

road_network = nx.Graph()
for node, coords in graph_nodes.items():
    road_network.add_node(node, lat=coords[0], lon=coords[1])
road_network.add_edges_from(road_edges)

time_based_risk = {
    (0, 6): 0.6,
    (6, 18): 1.2,
    (18, 24): 0.8
}

unsafe_reports = [
    {"lat": 18.5270, "lon": 73.8530, "intensity": 0.7, "description": "Dimly lit street"},
    {"lat": 18.5330, "lon": 73.8570, "intensity": 0.5, "description": "Isolated area at night"},
    
    {"lat": 18.5290, "lon": 73.8530, "intensity": 0.4, "description": "Occasional incidents reported"},
    {"lat": 18.5600, "lon": 73.8000, "intensity": 0.7, "description": "Isolated area, reports of theft"},
    {"lat": 18.6200, "lon": 73.8050, "intensity": 0.6, "description": "Late-night activity, poor visibility"},
    {"lat": 18.5050, "lon": 73.9000, "intensity": 0.5, "description": "Construction area, limited lighting"},
    {"lat": 18.6000, "lon": 73.7800, "intensity": 0.8, "description": "Dark alleys, reports of harassment"},
    {"lat": 18.6500, "lon": 73.7500, "intensity": 0.7, "description": "Less populated area, occasional incidents"},
    {"lat": 18.6300, "lon": 73.8300, "intensity": 0.6, "description": "Isolated park, reports of late night activities"},
    {"lat": 18.5700, "lon": 73.8700, "intensity": 0.5, "description": "underpass, low lighting"},  
    {"lat": 18.6800, "lon": 73.7800, "intensity": 0.6, "description": "Highway stretch, reports of speeding vehicles"}, # Ravet
    {"lat": 18.6400, "lon": 73.8800, "intensity": 0.5, "description": "Riverbank area, dimly lit at night"}, # Alandi
    {"lat": 18.5400, "lon": 73.9200, "intensity": 0.8, "description": "Remote outskirts, reports of robberies"}, # Wagholi
    {"lat": 18.5500, "lon": 73.7600, "intensity": 0.6, "description": "Under construction metro area, poor lighting and construction hazards"}, # Balewadi
    {"lat": 18.5000, "lon": 73.8800, "intensity": 0.7, "description": "Isolated park, late-night gatherings"},  # Hadapsar outskirts
    {"lat": 18.4700, "lon": 73.8700, "intensity": 0.6, "description": "Construction area, poor lighting and pathways"},  # Undri
    {"lat": 18.4500, "lon": 73.8500, "intensity": 0.5, "description": "Remote road, reports of speeding vehicles"},  # Kondhwa outskirts
    {"lat": 18.4800, "lon": 73.9000, "intensity": 0.8, "description": "Dense forest area, limited visibility at night"}, # Mohammadwadi
    {"lat": 18.4300, "lon": 73.8600, "intensity": 0.7, "description": "Isolated area, reports of theft and harassment"}, # Bibwewadi outskirts
    {"lat": 18.4600, "lon": 73.8300, "intensity": 0.6, "description": "Underpass, dimly lit and less crowded"}, # Katraj
    {"lat": 18.4900, "lon": 73.9200, "intensity": 0.5, "description": "Riverbank area, dimly lit and isolated"}, # Kharadi outskirts
    {"lat": 18.4400, "lon": 73.8800, "intensity": 0.8, "description": "Hilly area, reports of robberies and less traffic"}, # Saswad road.
    {"lat": 18.5270, "lon": 73.8400, "intensity": 0.7, "description": "Isolated alleyways, poor lighting and reports of petty crime"}, # Bhandarkar Road
]

safe_spaces = [
     {"name": "Tech Park Security Hub", "lat": 18.6250, "lon": 73.7950, "details": "Monitored area, security personnel present"},
    {"name": "Residential Complex Guard Post", "lat": 18.5100, "lon": 73.8950, "details": "Gated community, guarded entrance"},
    {"name": "Shopping Mall Security", "lat": 18.5900, "lon": 73.7750, "details": "Well-lit, security cameras and personnel"},
    {"name": "24/7 Police Station", "lat": 18.6400, "lon": 73.7450, "details": "Police presence, emergency services"},
    {"name": "School Campus Security", "lat": 18.6350, "lon": 73.8250, "details": "Guarded during school hours and after"},
    {"name": "Railway Station Police Post", "lat": 18.5650, "lon": 73.8650, "details": "Always staffed, railway police presence"},
    {"name": "Community Park Security", "lat": 18.5850, "lon": 73.7250, "details": "Patrolled park, security personnel present"}, # Pimple Saudagar park
    {"name": "Toll Plaza Security", "lat": 18.6750, "lon": 73.7750, "details": "24/7 presence, highway patrol"}, # Ravet Toll
    {"name": "Temple Security", "lat": 18.6350, "lon": 73.8750, "details": "Security personnel, CCTV surveillance"}, # Alandi temple area.
    {"name": "Large Residential complex gate", "lat": 18.5450, "lon": 73.9150, "details": "Security at main gate, 24/7"}, # Wagholi residential
    {"name": "Metro Station Security", "lat": 18.5550, "lon": 73.7550, "details": "Security staff, CCTV, well lit area"}, # Balewadi metro
    {"name": "Balewadi High Street Security", "lat": 18.5530, "lon": 73.7800, "details": "Shopping and dining area, Security personnel, CCTV"},
    {"name": "Karve Nagar Police Chowki", "lat": 18.5020, "lon": 73.8290, "details": "Police Chowki, Always on duty"},
    {"name": "Karve Road Petrol Pump 24/7", "lat": 18.5060, "lon": 73.8320, "details": "Petrol Pump, 24/7, CCTV"},
    {"name": "Bavdhan Residential Complex Gate", "lat": 18.5350, "lon": 73.7800, "details": "Gated Community, Security personnel"},
    {"name": "Pashan Residential Complex Gate", "lat": 18.5400, "lon": 73.8050, "details": "Gated Community, Security personnel"},
    {"name": "Community Center A", "lat": 18.5300, "lon": 73.8550, "details": "Open till 9 PM, security present"},
    {"name": "Trusted Cafe B", "lat": 18.5180, "lon": 73.8450, "details": "Staff aware and helpful, well-lit area"},
    {"name": "Police Chowki near Market", "lat": 18.5270, "lon": 73.8620, "details": "Always on duty"},
    {"name": "24/7 Hospital Emergency", "lat": 18.5800, "lon": 73.8200, "details": "Round-the-clock medical assistance"},
    {"name": "Residential Complex Security", "lat": 18.4950, "lon": 73.8850, "details": "Gated community, guarded entrance"},
    {"name": "Shopping Mall Security", "lat": 18.4650, "lon": 73.8650, "details": "Well-lit, security cameras and personnel"},
    {"name": "Police Station", "lat": 18.4450, "lon": 73.8450, "details": "Police presence, emergency services"},
    {"name": "Community Park Security", "lat": 18.4850, "lon": 73.8950, "details": "Patrolled park, security personnel present"},
    {"name": "24/7 Pharmacy", "lat": 18.4350, "lon": 73.8550, "details": "24/7 medical supplies and assistance"},
    {"name": "Bus Depot Security", "lat": 18.4550, "lon": 73.8250, "details": "Security personnel, CCTV surveillance"},
    {"name": "Riverfront Security", "lat": 18.4950, "lon": 73.9150, "details": "Patrolled riverfront area"},
    {"name": "Highway Patrol", "lat": 18.4350, "lon": 73.8750, "details": "Highway patrol presence"},
    {"name": "Police Station", "lat": 18.5285, "lon": 73.8505, "details": "Always open"},
    {"name": "Well-lit Cafe", "lat": 18.5340, "lon": 73.8560, "details": "Open till late"},
]

safe_taxi_stands = [
    {"name": "Taxi Stand 1", "lat": 18.5210, "lon": 73.8550, "notes": " A"},
    {"name": "Taxi Stand 2", "lat": 18.5300, "lon": 73.8510, "notes": " B"},
]

# --- Simulate safe bus routes with actual coordinate paths ---
safe_bus_routes = [
    {
        "name": "Route A",
        "path_coordinates": [
            (18.5204, 73.8567),  # Pune University
            (18.5218, 73.8552),  # Ganeshkhind Road
            (18.5235, 73.8535),  # Near COEP Chowk
            (18.5255, 73.8518),  # FC Road Entrance
            (18.5275, 73.8505),  # Deccan Gymkhana
            (18.5295, 73.8515),  # Near Garware Bridge
            (18.5315, 73.8530),  # Pune Railway Station
            (18.5335, 73.8545),  # Bund Garden Road
            (18.5350, 73.8550)   # Bund Garden
        ],
        "frequency": "Every 10 mins"
    },
    {
        "name": "Route B",
        "path_coordinates": [
            (18.5204, 73.8567),  # Pune University
            (18.5190, 73.8555),  # Senapati Bapat Road
            (18.5175, 73.8540),  # Chaturshrungi Temple Road Junction
            (18.5160, 73.8555),  # Gokhalenagar
            (18.5150, 73.8570),  # Model Colony Road
            (18.5165, 73.8585),  # Near Shivajinagar Railway Station
            (18.5180, 73.8600),  # Agarkar Bridge
            (18.5195, 73.8615)   # Near Pune Central Mall
        ],
        "frequency": "Every 15 mins"
    },
]

# --- Emergency Contacts Data (from emergency.py) ---
police_stations = [
    {"name": "Shivajinagar Police Station", "lat": 18.5387, "lon": 73.8573, "contact": "020-25511111"},
    {"name": "Deccan Gymkhana Police Station", "lat": 18.5178, "lon": 73.8441, "contact": "020-25652222"},
    {"name": "Swargate Police Station", "lat": 18.5033, "lon": 73.8601, "contact": "020-24453333"},
    {"name": "Kothrud Police Station", "lat": 18.5085, "lon": 73.8183, "contact": "020-25384444"},
    {"name": "Yerwada Police Station", "lat": 18.5670, "lon": 73.8778, "contact": "020-26685555"},
    {"name": "Khadki Police Station", "lat": 18.5654, "lon": 73.8451, "contact": "020-25876611"},
    {"name": "Baner Police Station", "lat": 18.5590, "lon": 73.7890, "contact": "020-27299900"},
    {"name": "Hinjewadi Police Station", "lat": 18.5912, "lon": 73.7381, "contact": "020-22985566"},
    {"name": "Wakad Police Station", "lat": 18.5998, "lon": 73.7722, "contact": "020-27443322"},
    {"name": "Bibwewadi Police Station", "lat": 18.4695, "lon": 73.8712, "contact": "020-24385588"},
    {"name": "Hadapsar Police Station", "lat": 18.5082, "lon": 73.9250, "contact": "020-26887744"},
    {"name": "Viman Nagar Police Chowky", "lat": 18.5663, "lon": 73.9132, "contact": "020-26789911"},
    {"name": "Camp Police Station", "lat": 18.5167, "lon": 73.8780, "contact": "020-26334455"},
    {"name": "Pimpri Police Station", "lat": 18.6272, "lon": 73.7999, "contact": "020-27452200"},
    {"name": "Chinchwad Police Station", "lat": 18.6301, "lon": 73.8071, "contact": "020-27489966"}
]


women_help_centers = [
    {"name": "Bharosa Cell", "lat": 18.5204, "lon": 73.8567},
    {"name": "Swayam Siddha Mahila Manch", "lat": 18.5132, "lon": 73.8552},
    {"name": "Aadhar Mahila Mandal", "lat": 18.5356, "lon": 73.8723},
    # ... more centers
]

emergency_contacts_list = [
    {"name": "Police Control Room", "number": "100"},
    {"name": "Women Helpline", "number": "1091"},
    {"name": "National Emergency Number", "number": "112"},
]

# Simulate user's trusted contacts (replace with actual user data)
trusted_contacts = [
    {"name": "Family Member 1", "number": "9356838390", "lat": 18.5250, "lon": 73.8600},
    {"name": "Friend 1", "number": "9322595377", "lat": 18.5150, "lon": 73.8500},
    {"name": "Friend 2", "number": "9423069642", "lat": 18.5300, "lon": 73.8700},
    # ... more trusted contacts with potential locations (if available)
]

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculates the distance between two coordinates."""
    return geopy.distance.geodesic((lat1, lon1), (lat2, lon2)).km

def find_nearest_locations(user_lat, user_lon, locations, num_results=3):
    """Finds the nearest locations using a priority queue (min-heap)."""
    distances = []
    for location in locations:
        distance = calculate_distance(user_lat, user_lon, location["lat"], location["lon"])
        heapq.heappush(distances, (distance, location))

    nearest_locations = []
    for _ in range(min(num_results, len(distances))):
        nearest_locations.append(heapq.heappop(distances)[1])

    return nearest_locations

def get_user_location():
    """Gets the user's location using geocoding."""
    geolocator = Nominatim(user_agent="emergency_app")
    try:
        location = geolocator.geocode("Pune") #default location, replace with actual user location.
        if location:
            return location.latitude, location.longitude
        else:
            print("Could not get location. Using Pune's default location.")
            return 18.5204, 73.8567 #Pune's general coordinates.
    except Exception as e:
        print(f"Error getting location: {e}. Using Pune's default location.")
        return 18.5204, 73.8567

def generate_emergency_map(user_lat, user_lon, nearest_police, nearest_help_centers, nearest_trusted):
    """Displays the locations on a map using Folium."""
    m = folium.Map(location=[user_lat, user_lon], zoom_start=12)

    folium.Marker([user_lat, user_lon], popup="Your Location", icon=folium.Icon(color="red")).add_to(m)

    # Police Stations
    police_group = folium.FeatureGroup(name="Nearest Police Stations")
    for station in nearest_police:
        popup_content = f"<b>{station['name']}</b><br>Contact: {station.get('contact', 'N/A')}"
        folium.Marker([station["lat"], station["lon"]], popup=popup_content, icon=folium.Icon(color="blue")).add_to(police_group)
        distance = calculate_distance(user_lat, user_lon, station['lat'], station['lon'])
        folium.CircleMarker(
            location=[station["lat"], station["lon"]],
            radius=5,
            color="blue",
            fill=False,
            tooltip=f"Approx. {distance:.2f} km away"
        ).add_to(police_group)
    police_group.add_to(m)

    # Women Help Centers
    help_center_group = folium.FeatureGroup(name="Nearest Women Help Centers")
    for center in nearest_help_centers:
        folium.Marker([center["lat"], center["lon"]], popup=center["name"], icon=folium.Icon(color="green")).add_to(help_center_group)
        distance = calculate_distance(user_lat, user_lon, center['lat'], center['lon'])
        folium.CircleMarker(
            location=[center["lat"], center["lon"]],
            radius=5,
            color="green",
            fill=False,
            tooltip=f"Approx. {distance:.2f} km away"
        ).add_to(help_center_group)
    help_center_group.add_to(m)

    # Trusted Contacts
    trusted_group = folium.FeatureGroup(name="Nearest Trusted Contacts")
    for contact in nearest_trusted:
        if "lat" in contact and "lon" in contact:
            popup_content = f"<b>{contact['name']}</b><br>Contact: {contact.get('number', 'N/A')}"
            folium.Marker([contact["lat"], contact["lon"]], popup=popup_content, icon=folium.Icon(color="purple")).add_to(trusted_group)
            distance = calculate_distance(user_lat, user_lon, contact['lat'], contact['lon'])
            folium.CircleMarker(
                location=[contact["lat"], contact["lon"]],
                radius=5,
                color="purple",
                fill=False,
                tooltip=f"Approx. {distance:.2f} km away"
            ).add_to(trusted_group)
        else:
            print(f"Warning: Location data not available for {contact['name']}")
    trusted_group.add_to(m)

    # Layer Control
    folium.LayerControl().add_to(m)

    return m._repr_html_()

def get_location_from_ip():
    ip_address = request.remote_addr
    params = {'apiKey': IP_GEOLOCATION_API_KEY, 'ip': ip_address}
    try:
        response = requests.get(IP_GEOLOCATION_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        if latitude and longitude:
            return float(latitude), float(longitude)
        else:
            print("Could not get coordinates from IP geolocation.")
            return None, None
    except requests.exceptions.RequestException as e:
        print(f"Error during IP geolocation request: {e}")
        return None, None

def get_destination_coordinates(destination_name):
    geolocator = Nominatim(user_agent="saferoute_app")
    try:
        location = geolocator.geocode(destination_name, exactly_one=True, timeout=5)
        if location:
            return location.latitude, location.longitude
        else:
            print(f"Could not find coordinates for '{destination_name}'.")
            return None, None
    except Exception as e:
        print(f"Error geocoding destination '{destination_name}': {e}")
        return None, None

def calculate_approximate_distance(lat1, lon1, lat2, lon2):
    return geopy.distance.geodesic((lat1, lon1), (lat2, lon2)).km

def find_closest_node(graph, target_lat, target_lon):
    closest_node = None
    min_distance = float('inf')
    for node, data in graph.nodes(data=True):
        lat, lon = data['lat'], data['lon']
        distance = calculate_approximate_distance(target_lat, target_lon, lat, lon)
        if distance < min_distance:
            min_distance = distance
            closest_node = node
    return closest_node

def get_current_time_risk_multiplier():
    now = datetime.now().hour
    for (start,end), multiplier in time_based_risk.items():
        if start <= now < end:
            return multiplier
    return 1.0

def find_safest_route(origin_lat, origin_lon, destination_name):
    end_lat, end_lon = get_destination_coordinates(destination_name)
    if not end_lat or not end_lon or not OPENROUTE_API_KEY:
        return [(origin_lat, origin_lon), (end_lat, end_lon)] if end_lat and end_lon else None, \
               calculate_approximate_distance(origin_lat, origin_lon, end_lat, end_lon) if end_lat and end_lon else None

    params = {
        "api_key": OPENROUTE_API_KEY,
        "start": f"{origin_lon},{origin_lat}",
        "end": f"{end_lon},{end_lat}",
        "preference": "shortest",  # You can change this to "safest" if the API supports it
        "format": "geojson"
    }
    try:
        response = requests.get(OPENROUTE_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if data and "features" in data and data["features"]:
            route_coordinates = data["features"][0]["geometry"]["coordinates"]
            # OpenRouteService returns [longitude, latitude], Folium expects [latitude, longitude]
            route_coordinates_swapped = [(lat, lon) for lon, lat in route_coordinates]
            distance = data["features"][0]["properties"]["summary"]["distance"] / 1000
            return route_coordinates_swapped, distance
        else:
            print("No route found by OpenRouteService.")
            return [(origin_lat, origin_lon), (end_lat, end_lon)], \
                   calculate_approximate_distance(origin_lat, origin_lon, end_lat, end_lon)
    except requests.exceptions.RequestException as e:
        print(f"Error during OpenRouteService request: {e}")
        return [(origin_lat, origin_lon), (end_lat, end_lon)], \
               calculate_approximate_distance(origin_lat, origin_lon, end_lat, end_lon)

def generate_safe_route_map(start_lat, start_lon, safest_route_coords, destination_coords, destination_name, unsafe_reports, safe_spaces, safe_bus_routes, safe_taxi_stands, emergency_contacts):
    m = folium.Map(location=[start_lat, start_lon], zoom_start=14)

    if safest_route_coords:
        folium.PolyLine(locations=safest_route_coords, color="blue", weight=5).add_to(m)

    heatmap_data = [[report["lat"], report["lon"], report["intensity"]] for report in unsafe_reports]
    HeatMap(heatmap_data, name="Unsafe Areas", min_opacity=0.5, radius=25, blur=15).add_to(m)

    for space in safe_spaces:
        folium.Marker(
            location=[space["lat"], space["lon"]],
            popup=f"<b>Safe Space:</b> {space['name']}<br>{space.get('details', '')}",
            icon=folium.Icon(color="green", icon="shield")
        ).add_to(m)

    for stand in safe_taxi_stands:
        folium.Marker(
            location=[stand["lat"], stand["lon"]],
            popup=f"<b>Taxi Stand:</b> {stand['name']}<br>{stand.get('notes', '')}",
            icon=folium.Icon(color="orange", icon="taxi")
        ).add_to(m)

    for route in safe_bus_routes:
        if "path_coordinates" in route and len(route["path_coordinates"]) > 1:
            folium.PolyLine(locations=route["path_coordinates"], color="purple", weight=3, dash_array="7, 7",
                            tooltip=f"Safe Bus Route: {route['name']} ({route['frequency']})").add_to(m)
            for coord in route["path_coordinates"]:
                folium.CircleMarker(location=coord, radius=2, color="purple", fill=True, fill_color="purple", fill_opacity=0.6).add_to(m)

    # Add Emergency Contacts to the map (using the basic list)
    for contact in emergency_contacts_list:
        folium.Marker(
            location=[start_lat + 0.001 * emergency_contacts_list.index(contact), start_lon + 0.001 * emergency_contacts_list.index(contact)], # Example placement
            popup=f"<b>Emergency:</b> {contact['name']}<br>Phone: {contact['number']}",
            icon=folium.Icon(color="red", icon="exclamation-triangle", prefix='fa')
        ).add_to(m)

    folium.Marker((start_lat, start_lon), popup="Your Current Location", icon=folium.Icon(color="red")).add_to(m)
    if destination_coords:
        folium.Marker(destination_coords, popup=f"Destination: {destination_name}", icon=folium.Icon(color="green")).add_to(m)

    folium.LayerControl().add_to(m)
    return m._repr_html_()

@app.route('/safest_route', methods=['GET', 'POST'])
def safest_route_page():
    map_html = ""
    route_info = ""
    origin_lat = session.get('user_lat', FIXED_START_LAT)
    origin_lon = session.get('user_lon', FIXED_START_LON)

    if request.method == 'POST':
        destination = request.form.get('destination')
        if destination:
            end_lat, end_lon = get_destination_coordinates(destination)
            if end_lat and end_lon:
                safest_route_coords, walking_distance = find_safest_route(origin_lat, origin_lon, destination)
                if safest_route_coords:
                    map_obj = generate_safe_route_map(origin_lat, origin_lon, safest_route_coords, (end_lat, end_lon), destination, unsafe_reports, safe_spaces, safe_bus_routes, safe_taxi_stands, emergency_contacts_list)
                    map_html = map_obj
                    route_info = f"Safest Route Found (Approx. {walking_distance:.2f} km)"
                else:
                    route_info = "Could not find a safe route."
            else:
                route_info = f"Could not find coordinates for '{destination}'."
        else:
            route_info = "Please enter a destination."

    default_map = folium.Map(location=[origin_lat, origin_lon], zoom_start=13)
    folium.Marker((origin_lat, origin_lon), popup="Your Current Location", icon=folium.Icon(color="red")).add_to(default_map)
    default_map_html = default_map._repr_html_()

    return render_template('safest_route.html', map_html=map_html if map_html else default_map_html, route_info=route_info)

# Initialize the SOS detector
sos_detector = SOSWordDetector()
sos_detector.insert("Help")
sos_detector.insert("Danger")
sos_detector.insert("Emergency")
sos_detector.insert("Save")
sos_detector.insert("Fire")
sos_detector.insert("Attack")

sos_detector = create_sos_detector()
is_sos_active = False  # make sure this is declared at global scope

@app.route('/sos', methods=['POST'])
def sos_check():
    global is_sos_active
    data = request.get_json()
    spoken_word = data.get('spoken_word', '')

    if spoken_word:
        words = spoken_word.split()
        for word in words:
            clean_word = word.strip().lower().translate(str.maketrans('', '', string.punctuation))
            if sos_detector.is_sos_word(clean_word):
                location = get_current_location()
                user_id = session.get('username', 'Guest')
                age = session.get('age', 'N/A')
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                send_sos_alert(user_id, age, location, clean_word)
                is_sos_active = True

                # Dynamic recipients calculation
                user_lat, user_lon = location[0], location[1]
                nearest_police = find_nearest_locations(user_lat, user_lon, police_stations, num_results=1)
                police_name = nearest_police[0]['name'] if nearest_police else "Local Police"
                police_contact = nearest_police[0].get('contact', '100')

                nearest_help = find_nearest_locations(user_lat, user_lon, women_help_centers, num_results=1)
                help_name = nearest_help[0]['name'] if nearest_help else "Women Helpline"

                recipients = [
                    f"{police_name} ({police_contact})",
                    f"{help_name} (1091)"
                ]
                for contact in trusted_contacts:
                    recipients.append(f"{contact['name']} ({contact['number']})")

                # Dispatch Twilio alert
                dispatch_twilio_sms(user_id, age, location, clean_word, recipients)

                return jsonify({
                    'message': f"SOS word '{clean_word}' detected and alert sent.",
                    'is_sos_active': True,
                    'details': {
                        'trigger_word': clean_word,
                        'location': location,
                        'user_id': user_id,
                        'age': age,
                        'timestamp': timestamp,
                        'recipients': recipients
                    }
                })

        if spoken_word.strip().lower() == 'stop' and is_sos_active:
            is_sos_active = False
            return jsonify({
                'message': "SOS tracking stopped.",
                'is_sos_active': False
            })

        return jsonify({
            'message': f"No SOS action for phrase '{spoken_word}'.",
            'is_sos_active': is_sos_active
        })

    else:
        return jsonify({
            'message': "No spoken word received.",
            'is_sos_active': is_sos_active
        })
    
    # --- Twilio SMS Alert dispatch helper ---
def dispatch_twilio_sms(user_id, age, location, spoken_word, recipients):
    """
    Dispatches simulated Twilio SMS alerts.
    If TWILIO credentials are configured, it will use real Twilio APIs.
    """
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_FROM_NUMBER = os.environ.get('TWILIO_FROM_NUMBER', '')

    maps_link = f"https://maps.google.com/?q={location[0]},{location[1]}" if location else "Unknown Location"
    message_body = (
        f"🚨 NAARI SURAKSHA EMERGENCY ALERT 🚨\n"
        f"User: {user_id} (Age: {age}) is in distress!\n"
        f"Trigger: '{spoken_word}'\n"
        f"Location: {maps_link}"
    )

    print(f"\n📲 --- TWILIO SMS ALERT DISPATCH SIMULATOR ---")
    print(f"Message content:\n{message_body}")
    print(f"Sending to emergency contacts:")
    for contact in recipients:
        print(f"  📤 Sent SMS to: {contact}")
    
    # Try actual API delivery if credentials are provided
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            for contact in recipients:
                import re
                numbers = re.findall(r'\+?\d+', contact)
                if numbers:
                    target_num = numbers[-1]
                    if not target_num.startswith('+'):
                        if len(target_num) == 10:
                            target_num = f"+91{target_num}"
                    client.messages.create(
                        body=message_body,
                        from_=TWILIO_FROM_NUMBER,
                        to=target_num
                    )
            print("🚀 Real Twilio SMS alerts sent successfully!")
        except Exception as e:
            print(f"⚠️ Failed to send real Twilio SMS: {e}")
    print("-------------------------------------------------\n")

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file part'}), 400
    file = request.files['audio']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Ensure upload directory exists in static/
    upload_dir = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"sos_{int(time.time())}.wav"
    filepath = os.path.join('static', 'uploads', filename)
    file.save(os.path.join(app.root_path, filepath))
    
    print(f"🎙️ Audio evidence uploaded and saved to: {filepath}")
    return jsonify({'status': 'success', 'filepath': f"/{filepath}"})

@app.route('/report_unsafe', methods=['POST'])
def report_unsafe():
    try:
        lat = float(request.form.get('lat'))
        lon = float(request.form.get('lon'))
        description = request.form.get('description', 'Safety Hazard Reported').strip()
        intensity = float(request.form.get('intensity', '5')) / 10.0 # scale 1-10 to 0.1-1.0
        
        new_report = {
            "lat": lat,
            "lon": lon,
            "intensity": intensity,
            "description": description
        }
        unsafe_reports.append(new_report)
        print(f"🗺️ New crowdsourced hazard reported: {new_report}")
        return redirect(url_for('safest_route_page'))
    except Exception as e:
        print(f"⚠️ Error adding crowdsourced report: {e}")
        return "Invalid hazard report data.", 400

# Auth Routes and Session Checks
@app.before_request
def require_login():
    allowed_routes = ['login', 'signup', 'home', 'static', 'save_location', 'upload_audio']
    if request.endpoint and request.endpoint not in allowed_routes:
        if 'username' not in session:
            return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        age = request.form['age']
        
        if not username or not password or not age:
            return render_template('signup.html', error="All fields are required.")
            
        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection(use_db=True)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password, age) VALUES (%s, %s, %s)',
                           (username, hashed_password, age))
            conn.commit()
        except pymysql.IntegrityError:
            conn.close()
            return render_template('signup.html', error="Username already exists.")
        conn.close()
        
        session['username'] = username
        session['age'] = age
        return redirect(url_for('home'))
        
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        conn = get_db_connection(use_db=True)
        cursor = conn.cursor()
        cursor.execute('SELECT password, age FROM users WHERE username = %s', (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row and check_password_hash(row[0], password):
            session['username'] = username
            session['age'] = row[1]
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Invalid username or password.")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/save_location', methods=['POST'])
def save_location():
    data = request.get_json()
    if data:
        session['user_lat'] = float(data.get('lat'))
        session['user_lon'] = float(data.get('lon'))
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 400

@app.route('/risk')
def risk_page():
    return render_template('risk.html')

@app.route('/set_timer', methods=['POST'])
def set_timer():
    destination = request.form['destination']
    hours = float(request.form['hours'])
    minutes = hours * 60
    
    user_id = session.get('username', 'Guest')
    age = session.get('age', 'N/A')
    lat = session.get('user_lat', FIXED_START_LAT)
    lon = session.get('user_lon', FIXED_START_LON)

    # Set the risk timer in the RiskTimer module
    RiskTimer.set_risk_timer(destination, minutes, user_id=user_id, age=age, lat=lat, lon=lon)

    # Store the destination in session if needed
    session['destination'] = destination

    # Redirect to the /challenge page after setting the timer
    return redirect(url_for('challenge'))

def send_alert(destination):
    print(f"🚨 ALERT: No correct response for '{destination}'. Notifying emergency contacts & police.")
    
    # Retrieve challenge details to send Twilio alerts
    data = RiskTimer.get_challenge_data()
    user_id = data.get('user_id', 'Guest')
    age = data.get('age', 'N/A')
    user_lat = data.get('lat', FIXED_START_LAT)
    user_lon = data.get('lon', FIXED_START_LON)
    location = (user_lat, user_lon)
    
    nearest_police = find_nearest_locations(user_lat, user_lon, police_stations, num_results=1)
    police_name = nearest_police[0]['name'] if nearest_police else "Local Police"
    police_contact = nearest_police[0].get('contact', '100')

    nearest_help = find_nearest_locations(user_lat, user_lon, women_help_centers, num_results=1)
    help_name = nearest_help[0]['name'] if nearest_help else "Women Helpline"

    recipients = [
        f"{police_name} ({police_contact})",
        f"{help_name} (1091)"
    ]
    for contact in trusted_contacts:
        recipients.append(f"{contact['name']} ({contact['number']})")
        
    dispatch_twilio_sms(user_id, age, location, f"Timer timeout at {destination}", recipients)
    
    try:
        import winsound
        winsound.Beep(1000, 700)
        winsound.Beep(1000, 700)
    except Exception as e:
        print(f"Beep error: {e}")

# Register the callback with RiskTimer
RiskTimer.register_alert_callback(send_alert)

@app.route('/challenge')
def challenge():
    # Retrieve active challenge data from RiskTimer
    data = RiskTimer.get_challenge_data()
    
    # If no challenge has started yet or isn't active, show the waiting/polling screen
    if not data or not data.get('active'):
        # If an alert was already sent for the last destination, display the status
        if data and data.get('alert_sent'):
            return f"<h3 style='text-align:center;'>🚨 Safety Check Failed! Alert has been sent for {data.get('destination')}. <a href='/risk'>Go Back</a></h3>"
        
        trigger_time = RiskTimer.get_next_trigger_time()
        remaining_str = "Calculating..."
        if trigger_time:
            remaining_secs = max(0, int(trigger_time - time.time()))
            if remaining_secs > 3600:
                remaining_str = f"{remaining_secs // 3600}h {(remaining_secs % 3600) // 60}m {remaining_secs % 60}s remaining"
            elif remaining_secs > 60:
                remaining_str = f"{remaining_secs // 60}m {remaining_secs % 60}s remaining"
            else:
                remaining_str = f"{remaining_secs}s remaining"
        else:
            remaining_str = "No active timer"

        return f"""
        <html>
        <head>
            <meta http-equiv="refresh" content="2">
            <title>Waiting for Challenge</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        </head>
        <body class="bg-light">
            <div class="container mt-5">
                <div class="card shadow p-4 rounded text-center">
                    <h2 class="text-primary">⏳ Waiting for Timer</h2>
                    <p class="mt-3">Your safety timer is currently running.</p>
                    <h3 class="text-danger my-3">{remaining_str}</h3>
                    <p class="text-muted">This page will automatically refresh and display the safety challenge when the timer expires.</p>
                    <div class="spinner-border text-primary my-3" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div class="mt-3">
                        <a href="/risk" class="btn btn-secondary">Go Back</a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

    # If it is active, check if it timed out (more than 10 seconds)
    elapsed = time.time() - data['timestamp']
    if elapsed > 10:
        if not data.get('alert_sent'):
            send_alert(data['destination'])
            data['alert_sent'] = True
        data['active'] = False
        return f"<h3 style='text-align:center;'>🚨 Timeout! Alert sent for {data['destination']}. <a href='/risk'>Go Back</a></h3>"

    if data.get('alert_sent'):
        return f"<h3 style='text-align:center;'>🚨 Alert already sent for {data['destination']}. <a href='/risk'>Go Back</a></h3>"

    # Otherwise, render the active challenge page
    time_left = max(0, 10 - elapsed)
    return render_template('challenge.html', word=data['word'], time_left=int(time_left))

@app.route('/submit_challenge', methods=['POST'])
def submit_challenge():
    user_input = request.form['user_input'].strip().lower()
    data = RiskTimer.get_challenge_data()

    if not data or not data.get('active'):
        return "<h3 style='text-align:center;'>No challenge active. <a href='/risk'>Go Back</a></h3>"

    correct_word = data['word'].lower()
    destination = data['destination']

    # Check timeout first
    if time.time() - data['timestamp'] > 10:
        if not data.get('alert_sent'):
            send_alert(destination)
            data['alert_sent'] = True
        data['active'] = False
        return f"<h3 style='text-align:center;'>🚨 Timeout! Alert sent for {destination}. <a href='/risk'>Go Back</a></h3>"

    if user_input == correct_word:
        data['active'] = False
        return f"<h3 style='text-align:center;'>✅ Safety Confirmed for {destination}! <a href='/risk'>Go Back</a></h3>"
    else:
        if not data.get('alert_sent'):
            send_alert(destination)
            data['alert_sent'] = True
        data['active'] = False
        return f"<h3 style='text-align:center;'>🚨 Incorrect! Alert sent for {destination}. <a href='/risk'>Go Back</a></h3>"


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/sos')
def sos_feature():
    return render_template('sos_interface.html') 

@app.route('/permissions')
def permissions():
    return render_template('permissions.html')

@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/emergency_contacts')
def emergency_contact_page():
    user_lat = session.get('user_lat')
    user_lon = session.get('user_lon')
    if not user_lat or not user_lon:
        user_lat, user_lon = get_current_location()
        
    nearest_police = find_nearest_locations(user_lat, user_lon, police_stations)
    nearest_help_centers = find_nearest_locations(user_lat, user_lon, women_help_centers)
    nearest_trusted = find_nearest_locations(user_lat, user_lon, trusted_contacts)
    map_html = generate_emergency_map(user_lat, user_lon, nearest_police, nearest_help_centers, nearest_trusted)
    return render_template('emergency_map.html', map_html=map_html, emergency_contacts=emergency_contacts_list)

if __name__ == '__main__':
     app.run(debug=True, use_reloader=False)