# RiskTimer.py
import heapq
import time
import random
import threading

risk_timer_heap = []
challenge_words = ["rescue", "safety", "secure", "escape", "protect", "shield", "guardian"]
challenge_data = {}
alert_callback = None

def register_alert_callback(callback):
    global alert_callback
    alert_callback = callback

def set_risk_timer(destination, minutes, user_id="Guest", age="N/A", lat=18.5204, lon=73.8567):
    global challenge_data
    trigger_time = time.time() + minutes * 60
    heapq.heappush(risk_timer_heap, (trigger_time, destination, user_id, age, lat, lon))
    # Reset any previous challenge when a new timer is set
    challenge_data = {}
    print(f"🧭 Risk timer set for '{destination}' in {minutes} minutes.")

def get_challenge_data():
    global challenge_data
    return challenge_data

def get_next_trigger_time():
    if risk_timer_heap:
        return risk_timer_heap[0][0]
    return None

def risk_timer_monitor():
    global challenge_data
    while True:
        try:
            if risk_timer_heap:
                current_time = time.time()
                timer, destination, user_id, age, lat, lon = risk_timer_heap[0]
                wait_time = timer - current_time
                
                if wait_time > 0:
                    time.sleep(min(1.0, wait_time))
                    continue
                
                # Timer expired! Pop it now.
                heapq.heappop(risk_timer_heap)

                # Trigger challenge
                challenge_word = random.choice(challenge_words)
                new_data = {
                    'destination': destination,
                    'word': challenge_word,
                    'timestamp': time.time(),
                    'alert_sent': False,
                    'active': True,
                    'user_id': user_id,
                    'age': age,
                    'lat': lat,
                    'lon': lon
                }
                challenge_data = new_data
                print(f"🛡️ Challenge activated for '{destination}': word '{challenge_word}'")

                # Active timeout monitor loop (10 seconds)
                timeout_limit = 10
                start_wait = time.time()
                while time.time() - start_wait < timeout_limit:
                    # If user correctly completed the challenge, 'active' will become False
                    if not challenge_data.get('active'):
                        break
                    time.sleep(0.5)

                # Trigger alert if the challenge is still active and no alert was sent
                if challenge_data.get('active') and not challenge_data.get('alert_sent'):
                    challenge_data['alert_sent'] = True
                    challenge_data['active'] = False
                    if alert_callback:
                        alert_callback(destination)
                    else:
                        print(f"🚨 ALERT: No correct response for '{destination}'. Notifying emergency contacts & police.")
            else:
                time.sleep(1)
        except Exception as e:
            print(f"❌ Error in risk timer monitor thread: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)

# Start background thread
threading.Thread(target=risk_timer_monitor, daemon=True).start()
