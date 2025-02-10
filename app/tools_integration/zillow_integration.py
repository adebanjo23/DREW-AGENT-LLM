import os
import asyncio
import aiohttp
from typing import Optional, List
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Property:
    address: str
    price: float
    bedrooms: int
    bathrooms: float
    living_area: float
    lot_area: Optional[float] = None
    lot_area_unit: Optional[str] = None
    property_type: str = ""
    zestimate: Optional[float] = None
    rent_estimate: Optional[float] = None
    days_on_zillow: int = 0
    listing_status: str = ""
    latitude: float = 0
    longitude: float = 0

    @classmethod
    def safe_int(cls, value, default=0):
        if value is None:
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default

    @classmethod
    def safe_float(cls, value, default=0.0):
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default


async def fetch_api1(session, location: str, status_type: str, home_type: str, days_on_market: int, api_key: str):
    url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
    params = {
        "location": location,
        "status_type": status_type,
        "home_type": home_type,
        "daysOn": str(days_on_market)
    }
    headers = {
        "x-rapidapi-host": "zillow-com1.p.rapidapi.com",
        "x-rapidapi-key": os.getenv("ZILLOW_1_API_KEY")
    }

    async with session.get(url, headers=headers, params=params) as response:
        if response.status == 200:
            return await response.json()
        return None


async def fetch_api2(session, location: str, status_type: str, api_key: str):
    url = "https://zillow56.p.rapidapi.com/search"
    params = {
        "location": location,
        "status": status_type,
        "listing_type": "by_agent",
        "sortSelection": "priorityscore",
        "output": "json",
        "doz": "any"
    }
    headers = {
        "x-rapidapi-host": "zillow56.p.rapidapi.com",
        "x-rapidapi-key": os.getenv("ZILLOW_2_API_KEY")
    }

    async with session.get(url, headers=headers, params=params) as response:
        if response.status == 200:
            return await response.json()
        return None


def parse_api1_response(data) -> List[Property]:
    properties = []
    if not data or not isinstance(data, dict):
        return properties

    props = data.get('props', []) if isinstance(data, dict) else []

    for prop in props:
        if not isinstance(prop, dict):
            continue

        address_parts = str(prop.get('address', '')).split(' ')
        cleaned_parts = [part for part in address_parts if not part.isdigit()]
        cleaned_address = ' '.join(cleaned_parts)

        property_obj = Property(
            address=cleaned_address,
            price=Property.safe_float(prop.get('price')),
            bedrooms=Property.safe_int(prop.get('bedrooms')),
            bathrooms=Property.safe_float(prop.get('bathrooms')),
            living_area=Property.safe_float(prop.get('livingArea')),
            lot_area=Property.safe_float(prop.get('lotAreaValue')),
            lot_area_unit=str(prop.get('lotAreaUnit', '')),
            property_type=str(prop.get('propertyType', '')),
            zestimate=Property.safe_float(prop.get('zestimate')),
            rent_estimate=Property.safe_float(prop.get('rentZestimate')),
            days_on_zillow=Property.safe_int(prop.get('daysOnZillow')),
            listing_status=str(prop.get('listingStatus', '')),
            latitude=Property.safe_float(prop.get('latitude')),
            longitude=Property.safe_float(prop.get('longitude'))
        )
        properties.append(property_obj)

    return properties


def parse_api2_response(data) -> List[Property]:
    properties = []
    if not data or not isinstance(data, dict):
        return properties

    results = data.get('results', []) if isinstance(data, dict) else []

    for prop in results:
        if not isinstance(prop, dict):
            continue

        address_parts = str(prop.get('streetAddress', '')).split(' ')
        cleaned_parts = [part for part in address_parts if not part.isdigit()]
        cleaned_address = ' '.join(cleaned_parts)

        property_obj = Property(
            address=cleaned_address,
            price=Property.safe_float(prop.get('price')),
            bedrooms=Property.safe_int(prop.get('bedrooms')),
            bathrooms=Property.safe_float(prop.get('bathrooms')),
            living_area=Property.safe_float(prop.get('livingArea')),
            property_type=str(prop.get('homeType', '')),
            zestimate=Property.safe_float(prop.get('zestimate')),
            rent_estimate=Property.safe_float(prop.get('rentZestimate')),
            days_on_zillow=Property.safe_int(prop.get('daysOnZillow')),
            latitude=Property.safe_float(prop.get('latitude')),
            longitude=Property.safe_float(prop.get('longitude'))
        )
        properties.append(property_obj)

    return properties


async def search_properties(
        location: str,
        status_type: str = "ForSale",
        home_type: str = "Houses",
        days_on_market: int = 7,
        limit: int = 3,
        api_key: str = os.getenv("RAPID_API_KEY")
) -> dict:
    async with aiohttp.ClientSession() as session:
        api1_task = fetch_api1(session, location, status_type, home_type, days_on_market, api_key)
        api2_task = fetch_api2(session, location, "forSale", api_key)

        api1_result, api2_result = await asyncio.gather(api1_task, api2_task, return_exceptions=True)

        properties = []

        if isinstance(api1_result, dict):
            properties = parse_api1_response(api1_result)

        if not properties and isinstance(api2_result, dict):
            properties = parse_api2_response(api2_result)

        return {
            "properties": properties[:limit] if properties else [],
            "message": "No listings available for the area" if not properties else None
        }


# Example usage
if __name__ == "__main__":
    async def main():
        try:
            results = await search_properties(
                location="soho",
                status_type="ForSale",
                home_type="Houses",
                days_on_market=7,
                limit=3
            )

            if results["message"]:
                print(results["message"])
                return

            for prop in results["properties"]:
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


    asyncio.run(main())