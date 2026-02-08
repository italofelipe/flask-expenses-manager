from typing import Any, Dict, Optional

import requests
from requests.exceptions import RequestException

from config import Config


class InvestmentService:
    @staticmethod
    def get_market_price(ticker: str) -> Optional[float]:
        """Consulta preço de mercado via BRAPI. Retorna None em caso de erro."""
        try:
            config = Config()
            resp = requests.get(
                f"https://brapi.dev/api/quote/{ticker.upper()}",
                headers={"Authorization": f"Bearer {config.BRAPI_KEY}"},
            )
            resp.raise_for_status()
            results = resp.json().get("results")
            if not results:
                return None
            return float(results[0].get("regularMarketPrice", 0))
        except RequestException:
            return None

    @staticmethod
    def calculate_estimated_value(data: Dict[str, Any]) -> Optional[float]:
        """
        Dado o payload validado, retorna o valor estimado:
        - Se tiver ticker e quantity, busca preço via get_market_price
        - Se não tiver ticker, usa value * quantity
        """
        ticker = data.get("ticker")
        quantity = data.get("quantity")
        value = data.get("value")

        if ticker and quantity is not None:
            price = InvestmentService.get_market_price(ticker)
            if price is None:
                return None
            return price * float(quantity)
        if value is not None and quantity is not None:
            return float(value) * float(quantity)
        return None
