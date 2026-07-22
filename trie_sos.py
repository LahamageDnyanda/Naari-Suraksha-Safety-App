import speech_recognition as sr
import time
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from datetime import datetime

# Constants and global state
CURRENT_USER_ID = "woman_user_123"
CURRENT_USER_GENDER = "female"
is_sos_active = False
sos_start_time = None
sos_last_location = None
TRACKING_DURATION = 60 * 5  # 5 minutes
LOCATION_UPDATE_INTERVAL = 10  # 10 seconds

# ---------------- Trie-based SOS Detector ----------------

class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False


class SOSWordDetector:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word):
        node = self.root
        for char in word.lower():
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True

    def is_sos_word(self, word):
        node = self.root
        for char in word.lower():
            if char not in node.children:
                return False
            node = node.children[char]
        return node.is_end_of_word

def create_sos_detector():
    detector = SOSWordDetector()
    sos_words = ["Help", "Danger", "Emergency", "Save", "Fire", "Attack"]
    for word in sos_words:
        detector.insert(word)
    return detector

# ---------------- Location Functions ----------------

def get_current_location():
    geolocator = Nominatim(user_agent="sos_app")
    try:
        pune_location = geolocator.geocode("Pune, Maharashtra, India", exactly_one=True, timeout=5)
        if pune_location:
            return pune_location.latitude, pune_location.longitude
        else:
            return 18.5204, 73.8567
    except Exception as e:
        print(f"⚠️ Error getting location: {e}")
        return 18.5204, 73.8567

# ---------------- SOS Alert Functions ----------------

def send_sos_alert(user_id, age, location, spoken_word):
    global is_sos_active, sos_start_time, sos_last_location
    print("🚨 SOS Alert Triggered!")
    print(f"👤 User ID: {user_id}")
    print(f"🎂 User Age: {age}")
    print(f"⚠️ SOS Word Detected: '{spoken_word}'")

    if location:
        latitude, longitude = location
        print(f"📍 Location: Latitude {latitude:.6f}, Longitude {longitude:.6f}")
        sos_last_location = location
    else:
        print("⚠️ Location not available.")

    is_sos_active = True
    sos_start_time = time.time()

def track_location():
    global sos_last_location
    if is_sos_active:
        current_location = get_current_location()
        if current_location != sos_last_location:
            sos_last_location = current_location
            latitude, longitude = current_location
            print(f"🛰️ Updated Location: Latitude {latitude:.6f}, Longitude {longitude:.6f} at {time.strftime('%H:%M:%S')}")

# ---------------- Speech Detection ----------------

def detect_speech_and_alert(sos_detector):
    global is_sos_active, sos_start_time

    if is_sos_active:
        if time.time() - sos_start_time >= TRACKING_DURATION:
            print("🛑 SOS tracking ended.")
            is_sos_active = False
            sos_start_time = None
            return

        print("📡 Listening for 'stop' command...")
        recognizer = sr.Recognizer()
        try:
            mic = sr.Microphone()
            with mic as source:
                recognizer.adjust_for_ambient_noise(source)
                print("👂 Listening...")
                audio = recognizer.listen(source, phrase_time_limit=10)
                text = recognizer.recognize_google(audio)
                print(f"🗣️ You said: {text}")
                if "stop" in text.lower():
                    print("✅ 'Stop' detected. Ending SOS.")
                    is_sos_active = False
                    sos_start_time = None
        except Exception as e:
            print(f"⚠️ Error in stop command recognition: {e}")
        return

    print("🎙️ Listening for SOS words...")
    recognizer = sr.Recognizer()

    try:
        mic = sr.Microphone()
        with mic as source:
            recognizer.adjust_for_ambient_noise(source)
            print("⌛ Speak up to 30 seconds...")
            audio = recognizer.listen(source, phrase_time_limit=30)

        text = recognizer.recognize_google(audio)
        print(f"🗣️ You said: {text}")

        for word in text.split():
            if sos_detector.is_sos_word(word):
                print("🚨 SOS word detected!")
                location = get_current_location()
                send_sos_alert(CURRENT_USER_ID, CURRENT_USER_GENDER, location, word)
                return

        print("✅ No SOS word detected.")

    except sr.UnknownValueError:
        print("😕 Could not understand speech.")
    except sr.RequestError as e:
        print(f"⚠️ Speech recognition error: {e}")
