"""
Abstract inventory strategy — Strategy Pattern.

Adding a new stock calculation method in future:
  1. Create a new class that inherits AbstractInventoryStrategy
  2. Implement compute_stock()
  3. Pass it to InventoryService
  No existing code needs to change.
"""

from abc import ABC, abstractmethod
from typing import List


class AbstractInventoryStrategy(ABC):
    """
    Base contract for all stock calculation strategies.
    Current implementations:
      - UsageBasedStrategy   : stock = purchases - manual_usage
      - ClosingStockStrategy : stock = verified via physical count

    Future implementations:
      - DishMappingStrategy  : stock = purchases - (dishes_sold × ingredients)
      - HybridStrategy       : combines multiple strategies with confidence scoring
    """

    @abstractmethod
    async def compute_stock(self, item_id: str) -> dict:
        """
        Compute current stock for a single item.
        Returns a dict with at minimum: qty_left, status
        """
        raise NotImplementedError

    @abstractmethod
    async def compute_all_stock(self) -> List[dict]:
        """Compute stock for all active items."""
        raise NotImplementedError
