import datetime
import uuid
from collections import defaultdict
from typing import Dict, List, Optional

import attr


class BatchReference(uuid.UUID):
    ...


def create_batch_reference() -> BatchReference:
    id = uuid.uuid4()
    return BatchReference(str(id))


class OrderReference(uuid.UUID):
    ...


def create_order_reference() -> OrderReference:
    id = uuid.uuid4()
    return OrderReference(str(id))


SkuName = str


@attr.s(auto_attribs=True, frozen=True)
class SKU:
    name: SkuName


@attr.s(auto_attribs=True, frozen=True)
class OrderLine:
    sku: SKU
    quantity: int

    def __str__(self) -> str:
        return f"<OrderLine {self.quantity}x {self.sku.name}>"


@attr.s(auto_attribs=True, frozen=True)
class Order:
    reference: OrderReference
    lines: List[OrderLine]

    def __str__(self) -> str:
        return f"<Order #{self.reference}>"


class DomainError(Exception):
    ...


class OutOfStockError(DomainError):
    ...


@attr.s(auto_attribs=True, frozen=True, order=False)
class Batch:
    reference: BatchReference
    sku: SKU
    quantity: int
    eta: Optional[datetime.date] = None

    def __str__(self) -> str:
        return f"<Batch {self.quantity}x {self.sku.name}>"

    def __lt__(self, other: "Batch") -> bool:
        if self.eta is None:
            return True

        if other.eta is None:
            return False

        return self.eta < other.eta


class Batches:
    batches: Dict[SkuName, List[Batch]] = {}

    def __init__(self, batches: List[Batch]) -> None:
        # Adding a batch happens less often than allocating an order line
        batch_dict = defaultdict(list)
        for batch in batches:
            batch_dict[batch.sku.name].append(batch)
        self.batches = {name: sorted(batches) for name, batches in batch_dict.items()}

        self._allocated_orders: Dict[OrderReference, Order] = {}

    def allocate(self, order: Order) -> List[BatchReference]:
        if order.reference in self._allocated_orders:
            return

        self._ensure_stock_is_available(order)

        # Every line has a different SKU
        # Batches are already sorted by preference
        for line in order.lines:
            batches = self.batches[line.sku.name]
            updated_batches = self._allocate_by_preference(batches, line)
            self.batches[line.sku.name] = updated_batches

        self._allocated_orders[order.reference] = order

        return [batch.reference for batch in updated_batches]

    @staticmethod
    def _allocate_by_preference(batches: List[Batch], line: OrderLine) -> List[Batch]:
        """Following allocation preferences, return batches after line allocation."""
        quantity_to_allocate = line.quantity
        allocated_quantity = 0
        updated_batches: List[Batch] = []

        # Assumption: a line will never need to be allocated to more than 1 batch
        for batch in batches:
            if quantity_to_allocate == allocated_quantity:
                updated_batches.append(batch)
                continue

            # TODO: check if batch has enough quanity to satisfy allocation
            updated_quantity = batch.quantity - quantity_to_allocate
            quantity_to_allocate = 0
            updated_batch = attr.evolve(batch, quantity=updated_quantity)
            updated_batches.append(updated_batch)

        return updated_batches

    def deallocate(self, order: Order) -> None:
        if order.reference not in self._allocated_orders:
            raise DomainError(
                f"Deallocation not possible: the order {order.reference} must "
                "be first allocated"
            )

    def _ensure_stock_is_available(self, order: Order) -> None:
        # Assumption: every line has a different SKU
        for line in order.lines:
            batches = self.batches.get(line.sku.name)

            if batches is None:
                raise DomainError(
                    "Allocation is not possible: there are no "
                    f"{line.sku.name} batches"
                )

            available_quantity = sum(batch.quantity for batch in batches)
            if available_quantity < line.quantity:
                raise OutOfStockError(
                    f"Allocation is not possible: {line.quantity} {line.sku.name} "
                    f"required but {available_quantity} available"
                )
        else:
            return
