from flask import Flask, request, render_template
import requests
from dash import Dash, html, dcc
from dash.dependencies import Input, Output
import plotly.graph_objs as go

app = Flask(__name__)

API_KEY = 'hcim65SyN9VGqzB0ULKzGBEwR5B0e8rE'
BASE_URL = 'http://dataservice.accuweather.com/'

dash_app = Dash(__name__, server=app, url_base_pathname='/dash/')
dash_app.layout = html.Div([
    html.Label("Количество дней прогноза (от 2 до 5):"),
    dcc.Input(
        id='days-input',
        type='number',
        min=2,  # Минимум 2, иначе на графике просто точки (так как нет почасовых данных)
        max=5,
        value=2,
        style={'margin-bottom': '20px', 'width': '100%'}
    ),
    html.Label("Выберите параметры для отображения:"),
    dcc.Checklist(
        id='parameter-checklist',
        options=[
            {'label': 'Температура (°C)', 'value': 'temperature'},
            {'label': 'Влажность (%)', 'value': 'humidity'},
            {'label': 'Скорость ветра (км/ч)', 'value': 'wind_speed'}
        ],
        value=['temperature', 'humidity', 'wind_speed'],
        labelStyle={'display': 'block'}
    ),
    html.Div(id='graphs-container', style={"display": "flex", "flex-wrap": "wrap"}),
    dcc.Graph(id='route-map', style={"width": "100%", "height": "600px", "margin-top": "20px"})
])

COLOR_SEQUENCE = [
    'red', 'blue', 'green', 'orange', 'purple',
    'brown', 'pink', 'gray', 'olive', 'cyan'
]

city_data = {}

@app.route('/', methods=['GET', 'POST'])
def index():
    weather_message = None
    cities_weather_data = {}
    formatted_weather_data = []

    if request.method == 'POST':
        cities = []
        for i in range(1, 6):
            city = request.form.get(f'city{i}')
            if city and city.strip():
                cities.append(city.strip())

        if not cities:
            weather_message = "Пожалуйста, введите хотя бы один город."
        else:
            try:
                for city in cities:
                    weather = get_weather_by_city(city)
                    cities_weather_data[city] = weather

                for city, weather in cities_weather_data.items():
                    forecast = weather['forecast'][0]
                    formatted_weather_data.append(
                        f"{city}: {forecast['temperature']}°C, Влажность {forecast['humidity']}%, Ветер {forecast['wind_speed']} км/ч"
                    )

                bad_weather = any(
                    check_bad_weather(**forecast)
                    for forecast in [weather['forecast'][0] for weather in cities_weather_data.values()]
                )

                if bad_weather:
                    weather_message = "Ой-ой, погода плохая."
                else:
                    weather_message = "Погода — супер!"

                global city_data
                city_data = cities_weather_data

            except ValueError as e:
                weather_message = f"Ошибка ввода данных: {str(e)}"
            except requests.exceptions.RequestException as e:
                weather_message = f"Ошибка подключения к серверу: {str(e)}"
            except Exception as e:
                weather_message = f"Произошла ошибка: {str(e)}. Пожалуйста, попробуйте снова."

    return render_template('index.html',
                           weather_message=weather_message,
                           formatted_weather_data=formatted_weather_data)

@dash_app.callback(
    [Output('graphs-container', 'children'),
     Output('route-map', 'figure')],
    [Input('parameter-checklist', 'value'),
     Input('days-input', 'value')]
)
def update_graphs(selected_parameters, days):
    if not selected_parameters:
        return [], go.Figure()

    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 2

    if days < 2 or days > 5:
        days = 2

    if not city_data:
        return [], go.Figure()

    graphs = []

    for parameter in selected_parameters:
        figure = go.Figure()
        for idx, (city, data) in enumerate(city_data.items()):
            all_days = [day['date'] for day in data['forecast']]
            all_values = [day[parameter] for day in data['forecast']]

            days_to_show = all_days[:days]
            values_to_show = all_values[:days]

            figure.add_trace(go.Scatter(
                x=days_to_show,
                y=values_to_show,
                mode='lines+markers',
                name=city,
                line=dict(color=COLOR_SEQUENCE[idx % len(COLOR_SEQUENCE)])
            ))

        figure.update_layout(
            title=parameter.capitalize(),
            xaxis_title='Дата',
            yaxis_title='Значение',
            height=400,
            xaxis=dict(tickformat="%d-%m-%Y")
        )
        graphs.append(dcc.Graph(figure=figure, style={"width": "100%", "margin": "10px"}))

    map_figure = go.Figure()

    latitudes = []
    longitudes = []
    colors = []

    for idx, (city, data) in enumerate(city_data.items()):
        forecast = data['forecast'][0]
        latitude = data['latitude']
        longitude = data['longitude']
        temperature = forecast['temperature']
        humidity = forecast['humidity']
        wind_speed = forecast['wind_speed']

        latitudes.append(latitude)
        longitudes.append(longitude)
        colors.append(COLOR_SEQUENCE[idx % len(COLOR_SEQUENCE)])

        map_figure.add_trace(go.Scattergeo(
            lon=[longitude],
            lat=[latitude],
            hoverinfo='text',
            text=f"{city}<br>Температура: {temperature}°C<br>Влажность: {humidity}%<br>Ветер: {wind_speed} км/ч",
            mode='markers',
            marker=dict(
                size=10,
                symbol='circle',
                color=colors[-1],
                line=dict(width=1, color='black')
            ),
            name=city
        ))

    if latitudes and longitudes:
        center_lat = sum(latitudes) / len(latitudes)
        center_lon = sum(longitudes) / len(longitudes)
    else:
        center_lat, center_lon = 0, 0

    map_figure.update_layout(
        title="Маршрут с прогнозами погоды",
        geo=dict(
            scope='world',
            projection_type='natural earth',
            showland=True,
            landcolor="rgb(243, 243, 243)",
            countrycolor="rgb(204, 204, 204)",
            center=dict(
                lat=center_lat,
                lon=center_lon
            ),
            showocean=True,
            oceancolor="LightBlue",
            lataxis=dict(showgrid=True, gridcolor='LightGrey'),
            lonaxis=dict(showgrid=True, gridcolor='LightGrey'),
        )
    )

    return graphs, map_figure

def get_weather_by_city(city_name):
    try:
        location_url = f'{BASE_URL}locations/v1/cities/search'
        location_params = {'apikey': API_KEY, 'q': city_name}
        location_response = requests.get(location_url, params=location_params)
        location_response.raise_for_status()
        location_data = location_response.json()

        if not location_data:
            raise ValueError(f"Не удалось найти город: {city_name}")

        location_key = location_data[0]['Key']
        geo_position = location_data[0]['GeoPosition']
        latitude = geo_position['Latitude']
        longitude = geo_position['Longitude']

        weather_url = f'{BASE_URL}forecasts/v1/daily/5day/{location_key}'
        weather_params = {'apikey': API_KEY, 'details': 'true'}
        weather_response = requests.get(weather_url, params=weather_params)
        weather_response.raise_for_status()
        weather_data = weather_response.json()

        forecasts = []
        for day in weather_data['DailyForecasts']:
            day_humidity = day['Day']['RelativeHumidity']['Average']
            night_humidity = day['Night']['RelativeHumidity']['Average']
            avg_humidity = (day_humidity + night_humidity) / 2

            temp_min_f = day['Temperature']['Minimum']['Value']
            temp_max_f = day['Temperature']['Maximum']['Value']
            temp_min_c = (temp_min_f - 32) * 5.0 / 9.0
            temp_max_c = (temp_max_f - 32) * 5.0 / 9.0
            avg_temp_c = (temp_min_c + temp_max_c) / 2

            wind_speed_kmh = day['Day']['Wind']['Speed']['Value'] * 1.60934

            forecasts.append({
                'date': day['Date'][:10],  # обрезаю время для удобства отображения
                'temperature': round(avg_temp_c, 2),
                'humidity': round(avg_humidity, 2),
                'wind_speed': round(wind_speed_kmh, 2)
            })

        return {
            "forecast": forecasts,
            "latitude": latitude,
            "longitude": longitude
        }

    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса для города {city_name}: {e}")
        raise RuntimeError(f"Ошибка запроса: {e}")

def check_bad_weather(temperature: float, wind_speed: float, humidity: float, **kwargs):
    if (temperature < 0 or temperature > 35 or wind_speed > 50
        or (humidity > 85 and temperature > 30)) or (humidity < 20 and wind_speed > 50):
        return True
    return False

if __name__ == '__main__':
    app.run(debug=True)
