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
    dcc.Checklist(
        id='parameter-checklist',
        options=[
            {'label': 'Температура', 'value': 'temperature'},
            {'label': 'Влажность', 'value': 'humidity'},
            {'label': 'Скорость ветра', 'value': 'wind_speed'}
        ],
        value=['temperature', 'humidity', 'wind_speed'],
        labelStyle={'display': 'block'}
    ),
    html.Div(id='graphs-container', style={"display": "flex", "flex-wrap": "wrap"})
])

city_data = {}
@app.route('/', methods=['GET', 'POST'])
def index():
    weather_message = None
    start_weather_data = None
    end_weather_data = None

    if request.method == 'POST':
        start_city = request.form.get('start')
        end_city = request.form.get('end')

        try:
            start_weather = get_weather_by_city(start_city)
            end_weather = get_weather_by_city(end_city)

            start_weather_data = f"{start_city}: {start_weather['temperature']}°C, Влажность {start_weather['humidity']}%, Ветер {start_weather['wind_speed']} км/ч"
            end_weather_data = f"{end_city}: {end_weather['temperature']}°C, Влажность {end_weather['humidity']}%, Ветер {end_weather['wind_speed']} км/ч"

            if check_bad_weather(**start_weather) or check_bad_weather(**end_weather):
                weather_message = "Ой-ой, погода плохая."
            else:
                weather_message = "Погода — супер!"

            global city_data
            city_data = {
                start_city: start_weather,
                end_city: end_weather
            }

        except ValueError as e:
            weather_message = f"Ошибка ввода данных: {str(e)}"
        except requests.exceptions.RequestException as e:
            weather_message = f"Ошибка подключения к серверу: {str(e)}"
        except Exception as e:
            weather_message = f"Произошла ошибка: {str(e)}. Пожалуйста, попробуйте снова."

    return render_template('index.html',
                           weather_message=weather_message,
                           start_weather_data=start_weather_data,
                           end_weather_data=end_weather_data)

@dash_app.callback(
    Output('graphs-container', 'children'),
    [Input('parameter-checklist', 'value')]
)
def update_graphs(selected_parameters):
    if not city_data:
        return []

    graphs = []

    for parameter in selected_parameters:
        figure = go.Figure()
        for city, data in city_data.items():
            figure.add_trace(go.Bar(
                x=[city],
                y=[data[parameter]],
                name=city
            ))
        figure.update_layout(
            title=parameter.capitalize(),
            yaxis_title='Значение',
            barmode='group',
            height=400
        )
        graphs.append(dcc.Graph(figure=figure, style={"width": "45%", "margin": "10px"}))

    return graphs

def get_weather_by_city(city_name):
    try:
        location_url = f'{BASE_URL}locations/v1/cities/search'
        location_params = {'apikey': API_KEY, 'q': city_name}
        location_response = requests.get(location_url, params=location_params)
        location_response.raise_for_status()
        location_data = location_response.json()

        if not location_data:
            raise ValueError("Не удалось найти город")

        location_key = location_data[0]['Key']

        weather_url = f'{BASE_URL}currentconditions/v1/{location_key}'
        weather_params = {'apikey': API_KEY, 'details': 'true'}
        weather_response = requests.get(weather_url, params=weather_params)
        weather_response.raise_for_status()
        weather_data = weather_response.json()

        if not weather_data:
            raise ValueError("Данные о погоде не найдены")

        weather_info = weather_data[0]
        return {
            "temperature": weather_info["Temperature"]["Metric"]["Value"],
            "humidity": weather_info["RelativeHumidity"],
            "wind_speed": weather_info["Wind"]["Speed"]["Metric"]["Value"],
            "rain_probability": weather_info.get("RainProbability", 0)
        }

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Ошибка запроса: {e}")

def check_bad_weather(temperature: float, wind_speed: float, rain_probability: float, humidity: float):
    if (temperature < 0 or temperature > 35 or wind_speed > 50 or rain_probability > 70
        or (humidity > 85 and temperature > 30)) or (humidity < 20 and wind_speed > 50):
        return True
    return False

if __name__ == '__main__':
    app.run(debug=True)
