import requests
import folium
from flask import render_template
import database as database
from database import app, API_URL
import plotly.express as px
import plotly.graph_objects as go

def get_icon_color(current_range_meters):
    if current_range_meters < 2000:
        return "red"
    elif current_range_meters < 5000:
        return "orange"
    elif current_range_meters < 10000:
        return "blue"
    else:
        return "green"
    
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
    bike_entries = database.Bike.query.all()
    chart_labels = [entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") for entry in bike_entries]
    n_bike_available = [entry.n_bike_available for entry in bike_entries]
    mean_distance_bike = [entry.mean_distance_bike for entry in bike_entries]
    total_distant = [entry.mean_distance_bike * entry.n_bike_available for entry in bike_entries]
    chart_1 = get_figures(chart_labels, n_bike_available, "Nombre de vélos disponibles", yaxis_title="Nombre de vélos")
    chart_2 = get_figures(chart_labels, mean_distance_bike, "Distance moyenne des vélos", yaxis_title="Distance (km)")
    chart_3 = get_figures(chart_labels, total_distant, "Distance totale des vélos", yaxis_title="Distance (km)")
    return render_template('chart.html', chart_1=chart_1, chart_2=chart_2, chart_3=chart_3)

def get_figures(x, y, name_figure, yaxis_title=""):
    fig = px.line(x=x, y=y)
    fig.update_layout(title=name_figure,
                   xaxis_title='Heure',
                   yaxis_title=yaxis_title)
    return fig.to_html(full_html=False)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080, use_reloader=False)
