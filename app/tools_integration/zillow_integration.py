import os

import requests
from typing import Optional, List
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Property:
    address: str
    price: float
    bedrooms: int
    bathrooms: int
    living_area: float
    lot_area: float
    lot_area_unit: str
    property_type: str
    zestimate: Optional[float]
    rent_estimate: Optional[float]
    days_on_zillow: int
    listing_status: str
    latitude: float
    longitude: float


def search_properties(
        location: str,
        status_type: str = "ForRent",
        home_type: str = "Houses",
        days_on_market: int = 7,
        limit: int = 3,
        api_key: str = os.getenv("RAPID_API_KEY")
) -> List[Property]:
    url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"

    querystring = {
        "location": location,
        "status_type": status_type,
        "home_type": home_type,
        "daysOn": str(days_on_market)
    }

    headers = {
        "x-rapidapi-host": "zillow-com1.p.rapidapi.com",
        "x-rapidapi-key": api_key
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        data = response.json()

        properties = []
        # Only process up to the limit
        # Inside the search_properties function, modify the property creation:
        # Inside the search_properties function, modify the property creation:
        for prop in data.get('props', [])[:limit]:
            # Get the address and remove house number
            full_address = prop.get('address', '')
            # Split address into parts
            address_parts = full_address.split(' ')
            # Filter out parts that are purely numeric
            cleaned_parts = [part for part in address_parts if not part.isdigit()]
            # Rejoin the parts
            cleaned_address = ' '.join(cleaned_parts)

            property_obj = Property(
                address=cleaned_address,  # Use the cleaned address instead
                price=prop.get('price'),
                bedrooms=prop.get('bedrooms'),
                bathrooms=prop.get('bathrooms'),
                living_area=prop.get('livingArea'),
                lot_area=prop.get('lotAreaValue'),
                lot_area_unit=prop.get('lotAreaUnit'),
                property_type=prop.get('propertyType'),
                zestimate=prop.get('zestimate'),
                rent_estimate=prop.get('rentZestimate'),
                days_on_zillow=prop.get('daysOnZillow'),
                listing_status=prop.get('listingStatus'),
                latitude=prop.get('latitude'),
                longitude=prop.get('longitude')
            )
            properties.append(property_obj)

        print(f"properties: {properties}")

        return properties

    except requests.exceptions.RequestException as e:
        raise Exception(f"Error fetching data from Zillow API: {str(e)}")


# Example usage:
if __name__ == "__main__":
    api_key = os.getenv("RAPID_API_KEY")

    try:
        results = search_properties(
            location="Calabasas, CA",
            status_type="ForSale",
            home_type="Houses",
            days_on_market=7,
            limit=3,  # Specify limit in the function call
            api_key=api_key
        )

        # Print results in a formatted way
        for prop in results:
            print(f"\nProperty: {prop.address}")
            print(f"Price: ${prop.price:,.2f}")
            print(f"Specs: {prop.bedrooms}bed/{prop.bathrooms}bath, {prop.living_area}sqft")
            print(f"Days on Zillow: {prop.days_on_zillow}")
            if prop.zestimate:
                print(f"Zestimate: ${prop.zestimate:,.2f}")
            if prop.rent_estimate:
                print(f"Rent Estimate: ${prop.rent_estimate:,.2f}/month")

    except Exception as e:
        print(f"Error: {str(e)}")