import openrouteservice
from openrouteservice import convert
import folium
from folium.plugins import HeatMap
import networkx as nx
from geopy.geocoders import Nominatim
from datetime import datetime
import webbrowser
import random

# OpenRouteService API Key
ORS_API_KEY = '5b3ce3597851110001cf6248fc9983571fcc4f99be09c0202832e14a'
client = openrouteservice.Client(key=ORS_API_KEY)

# --- Time-based risk multipliers ---
time_risk_multipliers = {
    (0, 6): 0.6,
    (6, 18): 1.2,
    (18, 24): 0.8
}


# --- Simulate user-reported unsafe areas (intensity 0-1) ---
unsafe_reports = [
    {"lat": 18.5250, "lon": 73.8600, "intensity": 0.8, "description": "Reported dimly lit after 9 PM"},
    {"lat": 18.5170, "lon": 73.8560, "intensity": 0.6, "description": "Few people around, poor lighting"},
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

# Simulate safe spaces
safe_spaces = [
    {"name": "Community Center A", "lat": 18.5300, "lon": 73.8550, "details": "Open till 9 PM, security present"},
    {"name": "Trusted Cafe B", "lat": 18.5180, "lon": 73.8450, "details": "Staff aware and helpful, well-lit area"},
    {"name": "Police Chowki near Market", "lat": 18.5270, "lon": 73.8620, "details": "Always on duty"},
    {"name": "24/7 Hospital Emergency", "lat": 18.5800, "lon": 73.8200, "details": "Round-the-clock medical assistance"},
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
]

# --- Simulate safe bus routes (with path nodes) ---
safe_bus_routes = [
    {"name": "Route 1A (Well-Lit Areas)", "path": [], "frequency": "Every 15 mins"},
    {"name": "Route 2B (Main Roads)", "path": [], "frequency": "Every 20 mins"},
]

# --- Simulate safe taxi pickup points ---
safe_taxi_stands = [
    {"name": "Designated Taxi Stand 1", "lat": 18.5360, "lon": 73.8570, "notes": "Verified drivers"},
    {"name": "Designated Taxi Stand 2", "lat": 18.5190, "lon": 73.8430, "notes": "24/7 service"},
    {"name": "Airport Taxi Pickup", "lat": 18.5800, "lon": 73.9100, "notes": "Authorized airport taxis"},
    {"name": "Railway Station Taxi Stand", "lat": 18.5000, "lon": 73.8700, "notes": "Prepaid taxi services"},
    {"name": "IT Park Taxi Zone", "lat": 18.6200, "lon": 73.8000, "notes": "Designated pickup for tech park employees"},
    {"name": "Bus Depot Taxi Stand", "lat": 18.5950, "lon": 73.7200, "notes": "Taxi stand near major bus depot"}, # Pimple Saudagar bus depot.
    {"name": "Highway Rest Stop Taxi", "lat": 18.6700, "lon": 73.7700, "notes": "Taxi services at highway rest stop"}, # Ravet highway rest stop
    {"name": "Pilgrim Taxi Stand", "lat": 18.6300, "lon": 73.8700, "notes": "Designated taxi stand for temple visitors"}, # Alandi temple taxi
    {"name": "Residential Hub Taxi", "lat": 18.5350, "lon": 73.9100, "notes": "Taxi stand in residential hub"}, # Wagholi residential hub
    {"name": "Metro Station Taxi", "lat": 18.5450, "lon": 73.7500, "notes": "Taxi stand near Metro station"}, # Balewadi Metro Taxi
]


def get_risk_multiplier():
    """Get the risk multiplier based on the current hour."""
    hour = datetime.now().hour
    for (start, end), mult in time_risk_multipliers.items():
        if start <= hour < end:
            return mult
    return 1.0

def get_coordinates(place_name):
    """Get the latitude and longitude of a place by its name using geopy."""
    geolocator = Nominatim(user_agent="safe_route_app")
    location = geolocator.geocode(place_name)
    if location:
        return location.latitude, location.longitude
    return None, None

def fetch_routes(start, end, alternatives=3):
    """Fetch alternative routes between start and end using OpenRouteService."""
    routes = client.directions(
        coordinates=[start, end],
        profile='foot-walking',
        format='geojson',
        optimize_waypoints=True,
        alternative_routes={"share_factor": 0.5, "target_count": alternatives}
    )
    return routes

def build_route_graph(route_geojson):
    """Build a graph from the route coordinates with random safety scores."""
    G = nx.DiGraph()
    coords = route_geojson['features'][0]['geometry']['coordinates']
    for i in range(len(coords) - 1):
        u = tuple(coords[i])
        v = tuple(coords[i + 1])
        dist = ((u[0] - v[0])**2 + (u[1] - v[1])**2) ** 0.5
        
        # Introducing variation in safety scores based on position (e.g., proximity to unsafe zones)
        safety_score = random.randint(5, 10)  # Simulate safety score based on position
        # Add more variation by considering proximity to unsafe areas
        for report in unsafe_reports:
            if abs(report['lat'] - u[0]) < 0.01 and abs(report['lon'] - u[1]) < 0.01:
                safety_score -= 2  # Decrease safety score near unsafe reports
        G.add_edge(u, v, distance=dist, safety=safety_score)
    return G

def score_route(graph):
    """Calculate the score of the route based on its safety and time-based risk multipliers."""
    multiplier = get_risk_multiplier()
    score = 0
    for u, v, data in graph.edges(data=True):
        # Lower weight for higher safety & time safety
        score += data['distance'] * ((10 - data['safety']) / 10) / multiplier
    return score

def display_map(routes, start_coords, end_coords, scores):
    """Display the routes on a Folium map with unsafe heatmaps and safe spaces."""
    # Define Pune's coordinates for map initialization
    pune_coords = (18.5204, 73.8567)  # Pune city center coordinates
    
    # Update the folium map to use Pune's coordinates
    fmap = folium.Map(location=pune_coords, zoom_start=13)  # Adjust zoom level to suit Pune city

    # Add start and end markers
    folium.Marker(location=start_coords[::-1], popup="Start", icon=folium.Icon(color="green")).add_to(fmap)
    folium.Marker(location=end_coords[::-1], popup="Destination", icon=folium.Icon(color="red")).add_to(fmap)

    # Show all route options
    for i, feature in enumerate(routes['features']):
        coords = feature['geometry']['coordinates']
        path = [(lat, lon) for lon, lat in coords]
        color = "blue" if i == scores.index(min(scores)) else "gray"
        folium.PolyLine(path, color=color, weight=5, tooltip=f"Route {i+1} Score: {scores[i]:.2f}").add_to(fmap)

    # Unsafe areas as heatmap
    heat_data = [[r["lat"], r["lon"], r["intensity"]] for r in unsafe_reports]
    HeatMap(heat_data, radius=20).add_to(fmap)

    # Safe spaces (focused around Pune)
    for space in safe_spaces:
        folium.Marker([space["lat"], space["lon"]], popup=space["name"], icon=folium.Icon(color="orange")).add_to(fmap)

    folium.LayerControl().add_to(fmap)
    fmap.save("interactive_safe_routes.html")
    webbrowser.open("interactive_safe_routes.html")

def main():
    """Main function to get user input, evaluate routes, and display the safest route on a map."""
    print("🏁 Safe Route Finder (OpenRouteService + Safety Graph)\n")
    source = input("Enter your starting location: ")
    destination = input("Enter your destination: ")

    src_lat, src_lon = get_coordinates(source)
    dst_lat, dst_lon = get_coordinates(destination)

    if not all([src_lat, src_lon, dst_lat, dst_lon]):
        print("❌ Could not find coordinates.")
        return

    start_coords = (src_lon, src_lat)
    end_coords = (dst_lon, dst_lat)

    routes = fetch_routes(start_coords, end_coords)
    route_scores = []

    print("\n🔍 Evaluating route safety...")

    for feature in routes['features']:
        G = build_route_graph({"features": [feature]})
        score = score_route(G)
        route_scores.append(score)

    best_index = route_scores.index(min(route_scores))
    print(f"\n✅ Best route is Route {best_index+1} with safety score {route_scores[best_index]:.2f}")
    
    display_map(routes, (src_lat, src_lon), (dst_lat, dst_lon), route_scores)

if __name__ == "__main__":
    main()
