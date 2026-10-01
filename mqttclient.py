#mqttclient.py — shared MQTT service
# Message contract (flat, one action per message):
#   {"camid": "cam1", "tagname": "loginreq", "tagvalue": true}

import json
import threading
import paho.mqtt.client as mqtt


class MqttService:
    def __init__(self, broker, port, request_topic, response_topic, handlers: dict, global_tags: set | None = None):
        """
        handlers:    {tagname: callable(camid, value)} — one entry per action. 
                     Unknown tagnames are logged and ignored.
        global_tags: tagnames that don't need a camid (e.g. a shutdown request that applies to the whole app). 
                     handler is still called as handler(camid, value) but camid may be None.
        """
        self.broker = broker
        self.port   = port
        self.request_topic  = request_topic
        self.response_topic = response_topic

        self.handlers    = handlers
        self.global_tags = global_tags or set()

        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message


    def start(self):
        threading.Thread(target=self._run, daemon=True).start()


    def _run(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_forever()
        except Exception as e:
            print(f"[MQTT] Could not connect: {e} — disabled.")


    def _on_connect(self, client, userdata, flags, rc):
        print(f"[MQTT] Connected (rc={rc}), subscribing to '{self.request_topic}'")
        client.subscribe(self.request_topic)


    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except Exception as e:
            print("[MQTT] Invalid JSON:", e)
            return

        camid    = payload.get("camid")
        tagname  = payload.get("tagname")
        tagvalue = payload.get("tagvalue")

        if tagname is None:
            print(f"[MQTT] Message missing 'tagname' — ignoring: {payload}")
            return

        handler = self.handlers.get(tagname)
        if handler is None:
            print(f"[MQTT] No handler registered for tagname '{tagname}' — ignoring.")
            return

        if not camid and tagname not in self.global_tags:
            print(f"[MQTT] Tag '{tagname}' requires a camid — ignoring: {payload}")
            return

        print(f"[MQTT] {tagname} (camid={camid}) → {tagvalue}")
        try:
            handler(camid, tagvalue)
        except Exception as e:
            print(f"[MQTT] Handler for '{tagname}' raised: {e}")


    def publish_result(self, payload: dict):
        print("[MQTT] Publishing:", payload)
        self.client.publish(self.response_topic, json.dumps(payload))