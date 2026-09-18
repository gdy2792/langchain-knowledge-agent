import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("WeatherMCP", log_level="ERROR")

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def _geocode(location: str) -> tuple[float, float, str]:
    response = httpx.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": location, "count": 1},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json().get("results")
    if not results:
        raise ValueError(f"Could not find a location matching '{location}'")
    match = results[0]
    label = ", ".join(
        part for part in [match.get("name"), match.get("admin1"), match.get("country")] if part
    )
    return match["latitude"], match["longitude"], label


@mcp.tool(
    name="get_current_weather",
    description="Get real-time current weather conditions for a named location (city, region, or landmark)",
)
def get_current_weather(
    location: str = Field(description="Location name, e.g. 'Chicago' or 'Chicago, IL'")
):
    latitude, longitude, label = _geocode(location)
    response = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
        },
        timeout=10,
    )
    response.raise_for_status()
    current = response.json()["current"]
    condition = WEATHER_CODES.get(current["weather_code"], "Unknown")

    return (
        f"Current weather in {label}: {condition}, "
        f"{current['temperature_2m']}°F (feels like {current['apparent_temperature']}°F), "
        f"{current['relative_humidity_2m']}% humidity, "
        f"wind {current['wind_speed_10m']} mph"
    )


@mcp.tool(
    name="get_weather_forecast",
    description="Get a multi-day weather forecast for a named location",
)
def get_weather_forecast(
    location: str = Field(description="Location name, e.g. 'Chicago' or 'Chicago, IL'"),
    days: int = Field(default=3, description="Number of forecast days to return (1-7)"),
):
    days = max(1, min(days, 7))
    latitude, longitude, label = _geocode(location)
    response = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "forecast_days": days,
        },
        timeout=10,
    )
    response.raise_for_status()
    daily = response.json()["daily"]

    lines = [f"{days}-day forecast for {label}:"]
    for i, date in enumerate(daily["time"]):
        condition = WEATHER_CODES.get(daily["weather_code"][i], "Unknown")
        lines.append(
            f"  {date}: {condition}, high {daily['temperature_2m_max'][i]}°F / "
            f"low {daily['temperature_2m_min'][i]}°F, "
            f"{daily['precipitation_probability_max'][i]}% chance of precipitation"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
