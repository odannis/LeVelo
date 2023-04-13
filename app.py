import requests
import folium
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
import os
import time
import threading
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bikes.db'
db = SQLAlchemy(app)

API_URL = "https://api.omega.fifteen.eu/gbfs/2.2/marseille/en/free_bike_status.json?&key=MjE0ZDNmMGEtNGFkZS00M2FlLWFmMWItZGNhOTZhMWQyYzM2"



class Bike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    n_bike_available = db.Column(db.Integer, nullable=False)
    mean_distance_bike = db.Column(db.Integer, nullable=False)

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
            time.sleep(60)  # Update every minute


with app.app_context():
    db.create_all()
update_thread = threading.Thread(target=update_database, daemon=True)
update_thread.start()


def get_icon_color(current_range_meters):
    if current_range_meters < 2000:
        return "red"
    elif current_range_meters < 5000:
        return "orange"
    elif current_range_meters < 10000:
        return "blue"
    else:
        return "green"
    
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
    print(bike_ranges)
    return bike_ranges
    
@app.route('/')
def index():
    response = requests.get(API_URL)
    data = response.json()
    bikes = data['data']['bikes']

    map = folium.Map(location=[43.296482, 5.36978], zoom_start=14, max_zoom=19, attr="test")
    latitude = []

    for bike in bikes:
        lat, lon = bike['lat'], bike['lon']
        while (lat, lon) in latitude:
            lat += 0.00003
            lon += 0.00003
        bike_id = bike['bike_id']
        current_range_meters = bike['current_range_meters']
        popup_text = f"Vélo {bike_id}<br>Portée actuelle : {current_range_meters / 1000} km"
        if bike["is_disabled"] == False:
            icon = folium.Icon(icon="bicycle", prefix="fa", color=get_icon_color(current_range_meters))
        else:
            icon = folium.Icon(icon="bicycle", prefix="fa", color="red")
        folium.Marker([lat, lon], popup=popup_text, icon=icon).add_to(map)
        latitude.append((lat, lon))

    return render_template("map.html", map=map._repr_html_())

@app.route("/chart")
def chart():
    bike_entries = Bike.query.all()

    chart_labels = [entry.timestamp.strftime("%Y-%m-%d %H:%M") for entry in bike_entries]
    n_bike_available = [entry.n_bike_available for entry in bike_entries]
    mean_distance_bike = [entry.mean_distance_bike for entry in bike_entries]
    total_distant = [entry.mean_distance_bike * entry.n_bike_available for entry in bike_entries]
    chart_script = f"""
    const ctx = document.getElementById('bikeChart').getContext('2d');
    const chart = new Chart(ctx, {{
        type: 'line',
        data: {{
            labels: {chart_labels},
            datasets: [
                {{
                    label: 'Nombre de vélo disponible',
                    data: {n_bike_available},
                    borderWidth: 1,
                    fill: false,
                    hidden: false,
                }},
                {{
                    label: 'Distance moyenne des vélos',
                    data: {mean_distance_bike},
                    borderWidth: 1,
                    fill: false,
                    hidden: true,
                }},
                {{
                    label: 'Distance totale des vélos',
                    data: {total_distant},
                    borderWidth: 1,
                    fill: false,
                    hidden: true,
                }}
            ]
        }},
        options: {{
            scales: {{
                x: {{
                    type: 'time',
                }},
            }}
        }}
    }});
    """

    return render_template("chart.html", chart_script=chart_script)




if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
