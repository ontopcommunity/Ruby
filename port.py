from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is alive!'

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run).start()
import threading, time, requests

def keep_alive():
    while True:
        try:
            requests.get("https://ruby-21lk.onrender.com")
        except:
            pass
        time.sleep(300)

threading.Thread(target=keep_alive).start()
