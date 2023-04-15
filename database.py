from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template
from datetime import datetime
import requests
import folium
from flask import Flask, render_template

import os
import time
import threading


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bikes.db'
db = SQLAlchemy(app)

API_URL = "https://api.omega.fifteen.eu/gbfs/2.2/marseille/en/free_bike_status.json?&key=MjE0ZDNmMGEtNGFkZS00M2FlLWFmMWItZGNhOTZhMWQyYzM2"


class Bike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    n_bike_available = db.Column(db.Integer, nullable=False)
    mean_distance_bike = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        bike_dict = {}
        for column in self.__table__.columns:
            bike_dict[column.name] = getattr(self, column.name)
        return bike_dict

def get_chart_data(bikes):
    bike_ranges = {
        "n_bike_available": 0,
        "mean_distance_bike": 0
    }

    l = []
    for bike in bikes:
        current_range_meters = bike["current_range_meters"]

        if bike["is_disabled"] == False:
            l.append(int(current_range_meters))
            bike_ranges["n_bike_available"] += 1
    
    bike_ranges["mean_distance_bike"] = sum(l) / len(l) / 1000
    return bike_ranges

def update_database():
    with app.app_context():
        while True:
            try:
                response = requests.get(API_URL)
                data = response.json()
                bikes = data["data"]["bikes"]
                chart_data = get_chart_data(bikes)

                bike_entry = Bike(
                    n_bike_available=chart_data["n_bike_available"],
                    mean_distance_bike=chart_data["mean_distance_bike"],
                )

                db.session.add(bike_entry)
                db.session.commit()
            except Exception as e:
                print(e)
            time.sleep(10)  # Update every minute


with app.app_context():
    db.create_all()

    update_thread = threading.Thread(target=update_database, daemon=True)
    update_thread.start()