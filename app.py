from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

API_KEY = 'hcim65SyN9VGqzB0ULKzGBEwR5B0e8rE'
BASE_URL = 'http://dataservice.accuweather.com/'


@app.route('/', methods=['GET'])
def get_weather():
    latitude = request.args.get('latitude', type=float)
    longitude = request.args.get('longitude', type=float)

    if latitude is None or longitude is None:
        return jsonify({"error": "Please provide latitude and longitude as query parameters"}), 400

    weather_data, status_code = get_weather_by_coordinates(latitude, longitude)

    bad_weather = check_bad_weather(
        temperature=weather_data['temperature_celsius'],
        wind_speed=weather_data['wind_speed_kph'],
        rain_probability=weather_data['rain_probability_percent'],
        humidity=weather_data['humidity']
    )
    weather_data['bad_weather'] = bad_weather

    return jsonify(weather_data), status_code


def get_weather_by_coordinates(latitude: float, longitude: float):
    try:
        location_url = f'{BASE_URL}/locations/v1/cities/geoposition/search'
        location_params = {
            'apikey': API_KEY,
            'q': f'{latitude},{longitude}'
        }
        location_response = requests.get(location_url, params=location_params)
        location_response.raise_for_status()
        location_data = location_response.json()

        if 'Key' not in location_data:
            return {"error": "Location key not found"}, 404

        location_key = location_data['Key']

        weather_url = f'{BASE_URL}/forecasts/v1/hourly/1hour/{location_key}'
        weather_params = {
            'apikey': API_KEY,
            'details': 'true'
        }
        weather_response = requests.get(weather_url, params=weather_params)
        weather_response.raise_for_status()
        weather_data = weather_response.json()

        if not weather_data:
            return {"error": "Weather data not found", "response": weather_data}, 404

        weather_info = weather_data[0]
        response = {
            "temperature_celsius": (weather_info["Temperature"]["Value"] - 32) * 5.0 / 9.0,
            "humidity": weather_info["RelativeHumidity"],
            "wind_speed_kph": weather_info["Wind"]["Speed"]["Value"] * 1.60934,
            "rain_probability_percent": weather_info["RainProbability"]
        }

        return response, 200

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}, 500

def check_bad_weather(temperature: float, wind_speed: float, rain_probability: float, humidity: float):
    if (temperature < 0 or temperature > 35 or wind_speed > 50 or rain_probability > 70
        or (humidity > 85 and temperature > 30)) or (humidity < 20 and wind_speed > 50):
        return True

    return False

if __name__ == '__main__':
    app.run(debug=True)
