import requests
import folium
from flask import render_template, request
import database as database
from database import app, API_URL
import plotly.express as px
import datetime
import pytz
from functools import wraps
import socket
import time
from waitress import serve
import threading
from flask_caching import Cache
from folium.plugins import LocateControl
import ssl
import os
import sys
import numpy as np


# Define the cache config keys, remember that it can be done in a settings file
app.config['CACHE_TYPE'] = 'SimpleCache'  # You can also use "FileSystemCache" or "RedisCache" etc...
# Initialize the cache
cache = Cache(app)
context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
path = os.path.dirname(os.path.realpath(sys.argv[0]))
context.load_cert_chain(path + '/cert.pem', path + '/key.pem')


def get_ip_address():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return ip_address

def log_ip(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        ip = request.remote_addr
        app.logger.info(f"IP address: {ip}")
        print(f"IP address: {ip}")
        return f(*args, **kwargs)
    return wrapped


def timeit(my_func):
    @wraps(my_func)
    def timed(*args, **kw):
    
        tstart = time.time()
        output = my_func(*args, **kw)
        tend = time.time()
        
        print('"{}" took {:.3f} s to execute\n'.format(my_func.__name__, (tend - tstart)))
        return output
    return timed

def convert_datetime_timezone(dt : datetime.datetime, tz1="UTC", tz2="Europe/Paris"):
    tz1 = pytz.timezone(tz1)
    tz2 = pytz.timezone(tz2)

    dt = tz1.localize(dt)
    dt = dt.astimezone(tz2)
    dt = dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt

def get_icon_color(current_range_meters):
    if current_range_meters < 2000:
        return "red"
    elif current_range_meters < 5000:
        return "orange"
    elif current_range_meters < 10000:
        return "blue"
    else:
        return "green"
    
def update_map():
    global map_out
    while True:
        try:
            t = time.time()
            response = requests.get(API_URL)
            data = response.json()
            bikes = data['data']['bikes']
            print("time request %s"%(time.time() - t))

            map = folium.Map(location=[43.296482, 5.36978], min_zoom=11, zoom_start=15,
                            max_zoom=19, attr="test", prefer_canvas=True)
            LocateControl(auto_start=True, flyTo=False, keepCurrentZoomLevel=True).add_to(map)
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

            map_out = map._repr_html_()
        except Exception as e:
            print("Update map fail : ", e)
        print("Temps d'exécution : ", time.time() - t)
        time.sleep(31)


@app.route('/')
@log_ip
def index():
    render_map = render_template("map.html", map=map_out)
    return render_map

@app.route('/chart', methods=['GET'])
@timeit
def chart(start_datetime=None, end_datetime=None):
    if "start_datetime" in request.args and "end_datetime" in request.args:
        start_datetime = datetime.datetime.fromisoformat(request.args.get('start_datetime'))
        end_datetime = datetime.datetime.fromisoformat(request.args.get('end_datetime'))
    else:
        start_datetime = datetime.datetime.now() - datetime.timedelta(days=3)
        end_datetime = datetime.datetime.now()
    chart_1, chart_2 = update_chart(start_datetime=start_datetime, end_datetime=end_datetime)
    return render_template('chart.html', chart_1=chart_1, chart_2=chart_2)

@timeit
def update_chart(start_datetime=None, end_datetime=None):
    #global chart_1, chart_2, chart_3
    print("update chart")
    with app.app_context():
        t = time.time()
        if start_datetime and end_datetime:
            bike_entries = database.Bike.query.filter(database.Bike.timestamp.between(start_datetime, end_datetime)).all()
        else:
            bike_entries = database.Bike.query.all()
        print("Time call database %s"%(time.time() - t))
        chart_labels = [entry.timestamp for entry in bike_entries]         
        n_bike_available = [entry.n_bike_available for entry in bike_entries]
        mean_distance_bike = [entry.mean_distance_bike for entry in bike_entries]
        #total_distant = [entry.mean_distance_bike * entry.n_bike_available for entry in bike_entries]
        chart_1 = get_figures(chart_labels, n_bike_available, "Nombre de vélos disponibles", yaxis_title="Nombre de vélos")
        chart_2 = get_figures(chart_labels, mean_distance_bike, "Distance moyenne des vélos", yaxis_title="Distance (km)")
        #chart_3 = get_figures(chart_labels, total_distant, "Distance totale des vélos", yaxis_title="Distance (km)")
    return chart_1, chart_2

@timeit
def get_figures(x, y, name_figure, yaxis_title=""):
    max_point = 1000
    l = np.linspace(0, len(x), max_point, dtype=int)
    x = [convert_datetime_timezone(x[i]) for i in l[:-1]]
    y = [np.mean(y[l[i]:l[i+1]]) for i in range(len(l)-1)]
    fig = px.line(x=x, y=y)
    fig.update_layout(title=name_figure,
                   xaxis_title='Heure',
                   yaxis_title=yaxis_title)
    return fig.to_html(full_html=False)




map_out = None, None, None, None

threading.Thread(target=update_map).start()

if __name__ == '__main__':
    port = 8080
    ip_address = get_ip_address()
    print(f"Starting server at https://{ip_address}:{port}")
    #serve(app, host="0.0.0.0", port=port)
    app.run(host='0.0.0.0', port=8080, use_reloader=False, ssl_context=context)
