import math, time, argparse
from threading import Thread
import os
import json
import paho.mqtt.client as mqtt

mqtt_address = "147.83.159.195"
mqtt_port = 24183


client = mqtt.Client()
client.connect(mqtt_address, mqtt_port, 60)
# Crea un mensaje JSON
mensaje = {	"id_dron": 	1,
        	"order": 	1,
            "route":	0}

# recibido de mapas
route = {"coordinates" : "[[0, 0], [2, 1], [2, 0]]",
         "type": "LineString"}

mensaje["route"] = route["coordinates"]

# Codifica el mensaje JSON a una cadena
mensaje_json = json.dumps(mensaje)

# Publica el mensaje en el topic "PTIN2023/A1/CAR"
client.publish("PTIN2023/VILANOVA/DRON/STARTROUTE", mensaje_json)

# Crea un mensaje JSON
mensaje = {	"id_dron": 	10,
            "hehe":	0}

mensaje["hehe"] = input("Escriu l'anomalia que vols testejar: ")

# Codifica el mensaje JSON a una cadena
mensaje_json = json.dumps(mensaje)
print(mensaje_json)

# Publica el mensaje en el topic "PTIN2023/A1/CAR"
client.publish("PTIN2023/VILANOVA/DRON/ANOMALIA", mensaje_json)

# Cierra la conexión MQTT
client.disconnect()