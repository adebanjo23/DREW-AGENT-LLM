import os

import requests
from dotenv import load_dotenv

load_dotenv()


def search_nearby_places(location, query_type="restaurants"):
    url = "https://google-map-places.p.rapidapi.com/maps/api/place/textsearch/json"

    params = {
        "query": f"{query_type} in {location}",
        "opennow": "true",
        "language": "en",
        "region": "en"
    }

    headers = {
        "x-rapidapi-host": "google-map-places.p.rapidapi.com",
        "x-rapidapi-key": os.getenv("RAPID_API_KEY")
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return None


def parse_place_details(results):
    places = []
    for place in results:
        place_info = {
            'name': place.get('name'),
            'address': place.get('formatted_address'),
            'rating': place.get('rating', 'No rating'),
            'total_ratings': place.get('user_ratings_total', 0),
            'price_level': '💰' * place.get('price_level', 0) or 'Not specified',
            'open_now': place.get('opening_hours', {}).get('open_now', 'Status unknown'),
            'types': [t for t in place.get('types', []) if t not in ['point_of_interest', 'establishment']]
        }
        places.append(place_info)
    return places


def format_places_response(places):
    formatted_results = []
    for place in places:
        status = "Open" if place['open_now'] else "Closed"
        formatted_place = (
            f"{place['name']}\n"
            f"📍 {place['address']}\n"
            f"⭐ {place['rating']} ({place['total_ratings']} reviews)\n"
            f"Status: {status}\n"
            f"Type: {', '.join(place['types'])}"
        )
        formatted_results.append(formatted_place)
    return formatted_results


def find_places(location, query_type="restaurants", limit=5):
    """
    Main function to search and format place results

    Args:
        location (str): Location to search in (e.g., "California", "Sydney")
        query_type (str): Type of place to search for (e.g., "restaurants", "coffee shops")
        limit (int): Maximum number of results to return (default: 5)

    Returns:
        list: Formatted strings with place information
    """
    # Get the raw response from the API
    # print(f"Searching for {query_type} in {location}")
    response_data = search_nearby_places(location, query_type)
    # print(f"{response_data}")

    if not response_data or 'results' not in response_data:
        return ["Sorry, no places found or there was an error with the search."]

    # Parse the response into structured data
    places = parse_place_details(response_data['results'][:limit])  # Add limit here

    # Format the places data into readable strings
    formatted_places = format_places_response(places)

    print(formatted_places)

    return formatted_places


# Example usage:
if __name__ == "__main__":
    # Example search
    location = "calabasas"
    place_type = "parks"

    results = find_places(location, place_type)

    # Print results
    print(f"Found {len(results)} places in {location}:")
    print("-" * 50)
    for result in results:
        print(result)
        print("-" * 50)
