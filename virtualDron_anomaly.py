import math, time, argparse
from threading import Thread
import os
# ---------------------------- #
import json
import paho.mqtt.client as mqtt
# ------------------------------------------------------------------------------ #

# Variables globals per forçar anomalies
anomalia_forcada = False
anomalia = ""

status_dron = {
    1: "loading",
    2: "unloading",
    3: "delivering",
	4: "awaiting",
	5: "returning",
   	6: "waits",
	7: "repairing",
	8: "alert",
    9: "delivered",
    10: "not delivered"
}

status_desc = {
    1: "loading - es troba en la colmena agafant el paquet.",
    2: "unloading - arribada al destí (client).",
    3: "delivering - camí cap al client.",
	4: "awaiting - esperant al client (QR).",
	5: "returning - tornada a la colmena.",
   	6: "waits - no fa res (situat en colmena)",
	7: "repairing - en taller per revisió o avaria.",
	8: "alert- possible avaria de camí o qualsevol situació anormal.",
    9: "delivered - el client ha rebut el paquet",
    10: "not delivered - el client no ha rebut el paquet" 
}

# API pel temps que fa
api_key = "1293361bdf356cc6360844d8bf8a9fcf"
base_url = "http://api.openweathermap.org/data/2.5/weather?"
complete_url = base_url + "appid=" + api_key + "&units=metric"

mqtt_address = os.environ.get('MQTT_ADDRESS')
mqtt_port = int(os.environ.get('MQTT_PORT'))
num_drones = int(os.environ.get('NUM_DRONES'))

# ------------------------------------------------------------------------------ #
mqtt_topic_city = str(os.environ.get('MQTT_TOPIC_CITY'))

STARTROUTE      = "PTIN2023/" + mqtt_topic_city + "DRON/STARTROUTE"
CONFIRMDELIVERY = "PTIN2023/" + mqtt_topic_city + "DRON/CONFIRMDELIVERY"
ANOMALIA        = "PTIN2023/" + mqtt_topic_city + "/DRON/ANOMALIA"

UPDATESTATUS    = "PTIN2023/" + mqtt_topic_city + "/DRON/UPDATESTATUS"
UPDATELOCATION  = "PTIN2023/" + mqtt_topic_city + "/DRON/UPDATELOCATION"
REPORTANOMALIA  = "PTIN2023/" + mqtt_topic_city + "/DRON/REPORTANOMALIA"
# ------------------------------------------------------------------------------ #

def get_angle(x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    return math.atan2(dy, dx)

def is_json(data):
    try:
        json.loads(data)
        return True
    except json.decoder.JSONDecodeError:
        return False
# ------------------------------------------------------------------------------ #

class vdron:

    def __init__(self, id) -> None:
        
        self.clientS = mqtt.Client()

        self.ID = id

        # State variables
        self.coordinates = None
        self.dron_return = False
        self.wait_client = False
        self.user_confirmed = False
        self.order_delivered = False
        self.start_coordinates = False
        self.time_wait_client = 180 # seconds

        # Initialize the battery level and the autonomy
        self.autonomy = 500
        self.battery_level = 100

    # Function to control the dron movement based on the angle
    def move_dron(self, angle, distance, battery_level, autonomy):
        
        # Calculate the distance traveled by the dron
        distance_traveled = math.sqrt(distance[0]**2 + distance[1]**2)

        # Calculate the battery usage based on the distance traveled
        battery_usage = distance_traveled / 0.025  # Assuming the dron uses 0.025 units of battery per meter
        
        # Update the battery level
        battery_level -= battery_usage

        # Update the autonomy based on the distance traveled and the battery usage
        autonomy -= distance_traveled / 100 * battery_level * 20

        stats = "DRON: %d Battery level: %.2f | Autonomy: %.2f | " % (self.ID, battery_level, autonomy)

        # Send signal to the dron to move in the appropriate direction based on the angle
        if angle > math.pi/4 and angle < 3*math.pi/4:
            # Move forward
            print(stats + "Moving forward")
        
        elif angle > -3*math.pi/4 and angle < -math.pi/4:
            # Move backward
            print(stats + "Moving backward")
        
        elif angle >= 3*math.pi/4 or angle <= -3*math.pi/4:
            # Turn left
            print(stats + "Turning left")
        
        else:
            # Turn right
            print(stats + "Turning right")
        
        return battery_level, autonomy

    def start_dron(self):
        x1, y1 = self.coordinates[0][1], self.coordinates[0][0]

        # Loop through each coordinate
        for i in range(1, len(self.coordinates)):
            if anomalia_forcada:
                break
            x2, y2 = self.coordinates[i][1], self.coordinates[i][0]

            # Calculate the distance between the current point and the next point
            distance = (x2 - x1, y2 - y1)

            # Calculate the angle between the current point and the next point
            angle = get_angle(x1, y1, x2, y2)

            # Control the dron movement based on the angle and update the battery level and the autonomy
            self.battery_level, self.autonomy = self.move_dron(angle, distance, self.battery_level, self.autonomy)

            # Send the dron position to Cloud
            self.send_location(self.ID, self.coordinates[i], 5 if self.dron_return else 3, self.battery_level, self.autonomy)

            # Update the current point
            x1, y1 = x2, y2

            # Add some delay to simulate the dron movement
            time.sleep(2)

        self.wait_client = True
        self.coordinates.reverse()

    def send_location(self, id, location, status, battery, autonomy):

        # Anomalia temps
        # Posem factor Random perque no fagi calls a la api cada dos per tres

        url = complete_url + "&lat=" + location[0] + "&lon=" + location[1]
        response = requests.get(url)
        x = response.json()
        if x["cod"] != "404":   
            y = x["main"]
            temperatura = y["temp"]
            full = x["weather"]
            condicio = full[0]["main"]
            if condicio != "Clear" and condicio != "Clouds" and temperatura < 35 and temperatura > 5:
                print("ALERTA: Condicions atmosferiques adverses.") 
                print("Temperatura: %d" % (temperatura))
                print("Condicions: %s" % (condicio))
                print("Dron en espera.")
        else:
            print("Avís: Hi ha hagut un error en la connexió amb l'API del temps.")

        self.clientS.connect(mqtt_address, mqtt_port, 60)

        msg = {	"id_dron": 	        id,
                "location_act": 	{
                    "latitude":     location[1],
                    "longitude":    location[0]
                },
                "status_num":       status,
                "status":           status_dron[status],
                "battery":          battery,
                "autonomy":         autonomy}

        mensaje_json = json.dumps(msg)
        self.clientS.publish(UPDATELOCATION, mensaje_json)
        self.clientS.disconnect()

    def update_status(self, id, status):

        self.clientS.connect(mqtt_address, mqtt_port, 60)

        msg = {	"id_dron":      id,
                "status_num":   status,
                "status":       status_dron[status]}

        mensaje_json = json.dumps(msg)

        self.clientS.publish(UPDATESTATUS, mensaje_json)
        print("DRON: " + str(id) + " | STATUS:  " + status_desc[status])
        
        self.clientS.disconnect()

    def send_anomaly_report(self, id, description):

        self.clientS.connect(mqtt_address, mqtt_port, 60)

        msg = {	"id_dron":      id,
                "result":   "ok",
                "description":       description}

        mensaje_json = json.dumps(msg)

        self.clientS.publish(REPORTANOMALIA, mensaje_json)
        print("DRON: " + str(id) + " | ANOMALIA:  " + anomalia + " -> " + description)
        
        self.clientS.disconnect()


    # ------------------------------------------------------------------------------ #

    def on_connect(self, client, userdata, flags, rc):

        if rc == 0:
            print(f"DRON {self.ID} | EDGE {mqtt_topic_city} connectat amb èxit.")
        client.subscribe("PTIN2023/#")

    def on_message(self, client, userdata, msg):
                
        if msg.topic == STARTROUTE:	

            if(is_json(msg.payload.decode('utf-8'))):
                
                payload = json.loads(msg.payload.decode('utf-8'))
                needed_keys = ["id_dron", "order", "route"]

                if all(key in payload for key in needed_keys):                
                    if self.ID == payload[needed_keys[0]] and payload[needed_keys[1]] == 1:
                        self.coordinates = json.loads(payload[needed_keys[2]])
                        print("RECEIVED ROUTE: " + str(self.coordinates[0]) + " -> " + str(self.coordinates[-1]))
                else:
                    print("FORMAT ERROR! --> PTIN2023/DRON/STARTROUTE")        
            else:
                print("Message: " + msg.payload.decode('utf-8'))

        elif msg.topic == CONFIRMDELIVERY:

            if(is_json(msg.payload.decode('utf-8'))):

                payload = json.loads(msg.payload.decode('utf-8'))
                needed_keys = ["id_dron", "status"]
                
                if all(key in payload for key in needed_keys):                
                    if self.ID == payload[needed_keys[0]]:
                        self.user_confirmed = (payload[needed_keys[1]] == 1)
                        print("USER RECEIVE CONFIRMED!", self.user_confirmed)
                else:
                    print("FORMAT ERROR! --> PTIN2023/DRON/CONFIRMDELIVERY") 

            else:
                print("Message: " + msg.payload.decode('utf-8'))
        
        elif msg.topic == ANOMALIA:

            if(is_json(msg.payload.decode('utf-8'))):
                
                global anomalia
                global anomalia_forcada

                payload = json.loads(msg.payload.decode('utf-8'))
                needed_keys = ["id_dron", "hehe"]
                
                if all(key in payload for key in needed_keys):                
                    if self.ID == payload[needed_keys[0]]:
                        anomalia_forcada = True
                        anomalia = payload[needed_keys[1]]
                        print("Rebuda anomalia forçada: %s" % (anomalia))
                else:
                    print("FORMAT ERROR! --> PTIN2023/DRON/CONFIRMDELIVERY") 

            else:
                print("Message: " + msg.payload.decode('utf-8'))

    def start(self):

        clientR = mqtt.Client()
        clientR.on_connect = self.on_connect
        clientR.on_message = self.on_message

        clientR.connect(mqtt_address, mqtt_port, 60)
        clientR.loop_forever()

# ------------------------------------------------------------------------------ #

    def control(self):

        while True:
            # Dos tipus de control, si hi ha anomalia o si no hi ha.
            if anomalia_forcada:
                if self.coordinates != None and not self.start_coordinates:
                    self.start_coordinates = True

                    # En proceso de carga ~ 5s
                    self.update_status(self.ID, 1)
                    time.sleep(5)

                    if anomalia == "cancel_betrayal":
                        anomalia_forcada = False
                        description = ("ATENCIÓ: Paquet en colmena cancel·lat. Ignoro i escanejo un altre")
                        send_anomaly_report(self, self.ID, description)
                        self.update_status(self.ID, 1)
                        time.sleep(5)
                    
                    # En reparto
                    self.update_status(self.ID, 3)
                    self.start_dron()

                time.sleep(0.25)

                if self.start_coordinates:
                                    
                    if self.wait_client:

                        # Esperando al cliente
                        self.update_status(self.ID, 4)
                        
                        waiting = 0
                        init = time.time()
                        while not self.user_confirmed and waiting < self.time_wait_client:
                            waiting = (time.time() - init)
                        
                        if self.user_confirmed:
                            # En proceso de descarga ~ 5s
                            self.update_status(self.ID, 2)
                            time.sleep(10)
                        
                            self.update_status(self.ID, 9)
                            time.sleep(5)
                            self.order_delivered = True
                        else:
                            self.order_delivered = False
                            self.update_status(self.ID, 10)
                        
                        self.wait_client = False
                        self.dron_return = True

                    elif self.dron_return:
                        
                        # Anomalia bateria baixa (<10%, >5%)
                        if anomalia == "set_battery_10":

                            battery = 10
                            anomalia_forcada = False
                            description = ("ATENCIÓ: Nivell de bateria baix, " + battery + "%. Accions: Retornant a la colmena...")
                            send_anomaly_report(self, self.ID, description)
                            self.update_status(self.ID, 5)
                            self.start_dron()

                            self.update_status(self.ID, 6)
                            self.start_coordinates = False

                            self.coordinates = None
                            self.dron_return = False
                            self.wait_client = False
                            self.user_confirmed = False
                            self.order_delivered = False
                            
                        # Anomalia bateria baixa (<5%)
                        elif anomalia == "set_battery_5":
                            battery = 5
                            anomalia_forcada = False
                            description = ("CRÍTIC: Nivell de bateria baix, " + battery + "%. Accions: Buscant refugi de forma immediata...")
                            send_anomaly_report(self, self.ID, description)
                            self.update_status(self.ID, 8)
                            self.start_dron()

                            self.update_status(self.ID, 6)
                            self.start_coordinates = False

                            self.coordinates = None
                            self.dron_return = False
                            self.wait_client = False
                            self.user_confirmed = False
                            self.order_delivered = False

                        elif anomalia == "make_rain" or anomalia == "make_thunder":
                            anomalia_forcada = False
                            description = ("CRÍTIC: Hi ha pluja / tempesta. Accions: Buscant refugi de forma immediata...")
                            send_anomaly_report(self, self.ID, description)
                            self.update_status(self.ID, 8)
                            self.start_dron()

                            self.update_status(self.ID, 6)
                            self.start_coordinates = False

                            self.coordinates = None
                            self.dron_return = False
                            self.wait_client = False
                            self.user_confirmed = False
                            self.order_delivered = False
                        
                        elif anomalia == "make_high_temp":
                            anomalia_forcada = False
                            description = ("CRÍTIC: Temperatura superior a 35 graus a l'ambient. Accions: Buscant refugi de forma immediata...")
                            send_anomaly_report(self, self.ID, description)
                            self.update_status(self.ID, 8)
                            self.start_dron()

                            self.update_status(self.ID, 6)
                            self.start_coordinates = False

                            self.coordinates = None
                            self.dron_return = False
                            self.wait_client = False
                            self.user_confirmed = False
                            self.order_delivered = False

                        elif anomalia == "make_low_temp":
                            anomalia_forcada = False
                            description = ("CRÍTIC: Temperatura inferior a 5 graus a l'ambient. Accions: Buscant refugi de forma immediata...")
                            send_anomaly_report(self, self.ID, description)
                            self.update_status(self.ID, 8)
                            self.start_dron()

                            self.update_status(self.ID, 6)
                            self.start_coordinates = False

                            self.coordinates = None
                            self.dron_return = False
                            self.wait_client = False
                            self.user_confirmed = False
                            self.order_delivered = False
                        
                        elif anomalia == "make_unknow_weather":
                            anomalia_forcada = False
                            description = ("ATENCIÓ: No és possible conèixer la informació meteorològica. Procedir amb cautela. Accions: Res.")
                            send_anomaly_report(self, self.ID, description)

                        elif anomalia == "explode_drone" or anomalia == "break_engine" or anomalia == "break_helix" or anomalia == "break_sensor" or anomalia == "unncomunicate":
                            description = ("CRÍTIC: El Drone ha sofert un problema tècnic. Codi d'error: " + anomalia + ". Accions: Es requereix que un tècnic es desplaçi a l'útima localització del drone.")
                            send_anomaly_report(self, self.ID, description)

                        elif anomalia == "put_obstacle":
                            anomalia_forcada = False
                            description = ("ATENCIÓ: Obstacle imprevist a la ruta.  Accions: Redirigint.")
                            send_anomaly_report(self, self.ID, description)
                            #Todo: Codi perque redirigeixi

                        else:

                            # Vuelta a a la colmena
                            self.update_status(self.ID, 5)
                            self.start_dron()

                            # En espera
                            self.update_status(self.ID, 6)
                            self.start_coordinates = False

                            self.coordinates = None
                            self.dron_return = False
                            self.wait_client = False
                            self.user_confirmed = False
                            self.order_delivered = False

                    else:  

                        if anomalia == "make_rain" or anomalia == "make_thunder":
                            anomalia_forcada = False
                            description = ("CRÍTIC: Hi ha pluja / tempesta. Accions: Buscant refugi de forma immediata...")
                            send_anomaly_report(self, self.ID, description)
                            self.update_status(self.ID, 8)
                            self.start_dron()

                            self.update_status(self.ID, 6)
                            self.start_coordinates = False

                            self.coordinates = None
                            self.dron_return = False
                            self.wait_client = False
                            self.user_confirmed = False
                            self.order_delivered = False

                        # Anomalia bateria baixa (<10%, >5%)
                        elif anomalia == "set_battery_10":

                            battery = 10
                            anomalia_forcada = False
                            description = ("ATENCIÓ: Nivell de bateria baix, " + battery + "%. Accions: Retornant a la colmena...")
                            send_anomaly_report(self, self.ID, description)
                            self.update_status(self.ID, 5)
                            self.start_dron()

                            self.update_status(self.ID, 6)
                            self.start_coordinates = False

                            self.coordinates = None
                            self.dron_return = False
                            self.wait_client = False
                            self.user_confirmed = False
                            self.order_delivered = False
                            
                        # Anomalia bateria baixa (<5%)
                        elif anomalia == "set_battery_5":
                            battery = 5
                            anomalia_forcada = False
                            description = ("CRÍTIC: Nivell de bateria baix, " + battery + "%. Accions: Buscant refugi de forma immediata...")
                            send_anomaly_report(self, self.ID, description)
                            self.update_status(self.ID, 8)
                            self.start_dron()

                            self.update_status(self.ID, 6)
                            self.start_coordinates = False

                            self.coordinates = None
                            self.dron_return = False
                            self.wait_client = False
                            self.user_confirmed = False
                            self.order_delivered = False

                        elif anomalia == "make_high_temp":
                            anomalia_forcada = False
                            description = ("CRÍTIC: Temperatura superior a 35 graus a l'ambient. Accions: Buscant refugi de forma immediata...")
                            send_anomaly_report(self, self.ID, description)
                            self.update_status(self.ID, 8)
                            self.start_dron()

                            self.update_status(self.ID, 6)
                            self.start_coordinates = False

                            self.coordinates = None
                            self.dron_return = False
                            self.wait_client = False
                            self.user_confirmed = False
                            self.order_delivered = False

                        elif anomalia == "make_low_temp":
                            anomalia_forcada = False
                            description = ("CRÍTIC: Temperatura inferior a 5 graus a l'ambient. Accions: Buscant refugi de forma immediata...")
                            send_anomaly_report(self, self.ID, description)
                            self.update_status(self.ID, 8)
                            self.start_dron()

                            self.update_status(self.ID, 6)
                            self.start_coordinates = False

                            self.coordinates = None
                            self.dron_return = False
                            self.wait_client = False
                            self.user_confirmed = False
                            self.order_delivered = False
                        
                        elif anomalia == "make_unknow_weather":
                            anomalia_forcada = False
                            description = ("ATENCIÓ: No és possible conèixer la informació meteorològica. Procedir amb cautela.  Accions: Res.")
                            send_anomaly_report(self, self.ID, description)

                        elif anomalia == "explode_drone" or anomalia == "break_engine" or anomalia == "break_helix" or anomalia == "break_sensor" or anomalia == "unncomunicate":
                            description = ("CRÍTIC: El Drone ha sofert un problema tècnic. Codi d'error: " + anomalia + ". Accions: Es requereix que un tècnic es desplaçi a l'útima localització del drone.")
                            send_anomaly_report(self, self.ID, description)
                        
                        elif anomalia == "put_obstacle":
                            anomalia_forcada = False
                            description = ("ATENCIÓ: Obstacle imprevist a la ruta.  Accions: Redirigint.")
                            send_anomaly_report(self, self.ID, description)
                            #Todo: Codi perque redirigeixi

                        # Queda escriure 4 anomalies mes
                        


            else:
                if self.coordinates != None and not self.start_coordinates:
                    self.start_coordinates = True

                    # En proceso de carga ~ 5s
                    self.update_status(self.ID, 1)
                    time.sleep(5)

                    # En reparto
                    self.update_status(self.ID, 3)
                    self.start_dron()

                time.sleep(0.25)

                if self.start_coordinates:
                                    
                    if self.wait_client:

                        # Esperando al cliente
                        self.update_status(self.ID, 4)
                        
                        waiting = 0
                        init = time.time()
                        while not self.user_confirmed and waiting < self.time_wait_client:
                            waiting = (time.time() - init)
                        
                        if self.user_confirmed:
                            # En proceso de descarga ~ 5s
                            self.update_status(self.ID, 2)
                            time.sleep(10)
                        
                            self.update_status(self.ID, 9)
                            time.sleep(5)
                            self.order_delivered = True
                        else:
                            self.order_delivered = False
                            self.update_status(self.ID, 10)
                        
                        self.wait_client = False
                        self.dron_return = True

                    elif self.dron_return:
                        
                        # Vuelta a a la colmena
                        self.update_status(self.ID, 5)
                        self.start_dron()

                        # En espera
                        self.update_status(self.ID, 6)
                        self.start_coordinates = False

                        self.coordinates = None
                        self.dron_return = False
                        self.wait_client = False
                        self.user_confirmed = False
                        self.order_delivered = False

if __name__ == '__main__':

    threads = []

    for i in range(1, num_drones+1):
        dron = vdron(i)
        API = Thread(target=dron.start)
        CTL = Thread(target=dron.control)
        threads.append(API)
        threads.append(CTL)
        API.start()
        CTL.start()

    for t in threads:
        t.join()