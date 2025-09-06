"""HTTP client for 西安水务."""
import logging
from datetime import datetime
import aiohttp
import async_timeout
import json

from .const import API_ENDPOINT

_LOGGER = logging.getLogger(__name__)

class XianWaterClient:
    """西安水务 API client."""

    def __init__(self, client_code, client_type, cid):
        """Initialize the client."""
        self.client_code = client_code
        self.client_type = client_type
        self.cid = cid
        self.session = None

    async def async_get_data(self):
        """Get data from the API."""
        if self.session is None:
            self.session = aiohttp.ClientSession()

        payload = {
            "clientCode": self.client_code,
            "clientType": self.client_type,
            "cid": self.cid,
            "page": {
                "current": 1,
                "size": 10
            }
        }

        try:
            async with async_timeout.timeout(120):
                response = await self.session.post(
                    API_ENDPOINT,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response_json = await response.json()
                
                if not response_json.get("success", False):
                    _LOGGER.error("API request failed: %s", response_json.get("message", "Unknown error"))
                    return None
                
                return self._process_data(response_json)
        except aiohttp.ClientError as err:
            _LOGGER.error("Error requesting data from API: %s", err)
            return None
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error: %s", err)
            return None

    def _process_data(self, response_json):
        """Process the API response data."""
        try:
            records = response_json.get("resultData", {}).get("records", [])
            if not records:
                _LOGGER.warning("No records found in API response")
                return None

            data = [{"date": record["pdate"], "cost": record["rlje"]} for record in records]
            return self._calculate_water_usage(data)
        except KeyError as err:
            _LOGGER.error("Missing expected field in API response: %s", err)
            return None

    def _calculate_water_usage(self, data):
        """Calculate water usage statistics."""
        try:
            first_date = datetime.strptime(data[0]["date"], "%Y-%m-%d")
            last_date = datetime.strptime(data[-1]["date"], "%Y-%m-%d")
            s1 = abs((first_date - last_date).days)
            
            if s1 == 0:
                _LOGGER.warning("Cannot calculate usage: first and last dates are the same")
                return None
            
            a = sum(float(record["cost"]) for record in data[1:])
            c = a / s1  # Daily cost
            
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            s2 = abs((today - first_date).days)
            
            b = float(data[0]["cost"])
            balance = b - c * s2
            usage_days = balance / c if c > 0 else 0
            
            return {
                "price": round(c, 2),
                "balance": round(balance, 2),
                "usage_days": int(usage_days),
                "data": data
            }
        except (ValueError, ZeroDivisionError) as err:
            _LOGGER.error("Error calculating water usage: %s", err)
            return None

    async def async_close(self):
        """Close the session."""
        if self.session:
            await self.session.close()
            self.session = None