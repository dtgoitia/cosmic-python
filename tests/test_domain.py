import datetime
from typing import List, Optional

import attr
import pytest

from cosmic_python.domain import (
    SKU,
    Batch,
    Batches,
    DomainError,
    Order,
    OrderLine,
    OutOfStockError,
    create_batch_reference,
    create_order_reference,
)


@pytest.fixture
def now() -> datetime.date:
    return datetime.datetime.now()


@pytest.fixture
def later(now) -> datetime.datetime:
    return now + datetime.timedelta(hours=1)


@pytest.fixture
def tomorrow(now) -> datetime.datetime:
    return now + datetime.timedelta(days=1)


def create_batch(
    sku: SKU, quantity: int, eta: Optional[datetime.datetime] = None
) -> Batch:
    return Batch(
        reference=create_batch_reference(),
        sku=sku,
        quantity=quantity,
        eta=eta,
    )


def create_order(lines: List[OrderLine]) -> Order:
    return Order(reference=create_order_reference(), lines=lines)


def test_reduce_batch_quantity_allocation():
    small_table = SKU(name="SMALL-TABLE")

    batch = create_batch(sku=small_table, quantity=20)
    batches = Batches([batch])

    order_line = OrderLine(sku=small_table, quantity=2)
    order = create_order(lines=[order_line])

    batches.allocate(order)

    updated_batch = attr.evolve(batch, quantity=18)
    assert batches.batches[small_table.name] == [updated_batch]


def test_order_can_only_be_allocaed_once():
    blue_vase = SKU(name="BLUE-VASE")

    batch = create_batch(sku=blue_vase, quantity=10)
    batches = Batches([batch])

    order_line = OrderLine(sku=blue_vase, quantity=2)
    order = create_order(lines=[order_line])

    batches.allocate(order)

    updated_batch = attr.evolve(batch, quantity=8)
    assert batches.batches[blue_vase.name] == [updated_batch]

    batches.allocate(order)

    assert batches.batches[blue_vase.name] == [updated_batch]


def test_allocate_errors_if_not_enough_stock_available():
    blue_cushion = SKU(name="BLUE-CUSHION")

    batch = create_batch(sku=blue_cushion, quantity=1)
    batches = Batches([batch])

    order_line = OrderLine(sku=blue_cushion, quantity=2)
    order = create_order(lines=[order_line])

    with pytest.raises(OutOfStockError) as e:
        batches.allocate(order)

    exc = e.value

    assert exc.args == (
        "Allocation is not possible: 2 BLUE-CUSHION required but 1 available",
    )


def test_cannot_allocate_if_skus_do_not_match():
    chair = SKU(name="ROMAN-CHAIR")
    table = SKU(name="GLASS-TABLE")

    batch = create_batch(sku=chair, quantity=1)
    batches = Batches([batch])

    order_line = OrderLine(sku=table, quantity=2)
    order = create_order(lines=[order_line])

    with pytest.raises(DomainError) as e:
        batches.allocate(order)

    exc = e.value

    assert exc.args == ("Allocation is not possible: there are no GLASS-TABLE batches",)


def test_can_only_deallocate_allocated_lines():
    chair = SKU(name="ROMAN-CHAIR")
    table = SKU(name="GLASS-TABLE")

    batch = create_batch(sku=chair, quantity=1)
    batches = Batches([batch])

    order_line = OrderLine(sku=table, quantity=2)
    order = create_order(lines=[order_line])

    with pytest.raises(DomainError) as e:
        batches.deallocate(order)

    exc = e.value

    assert exc.args == (
        f"Deallocation not possible: the order {order.reference} must be first allocated",
    )


def test_prefers_current_stock_batches_to_shipments(later):
    clock = SKU(name="RETRO-CLOCK")

    in_stock_batch = create_batch(clock, 100)
    shipment_batch = create_batch(clock, 100, eta=later)
    batches = Batches([in_stock_batch, shipment_batch])

    order_line = OrderLine(sku=clock, quantity=10)
    order = create_order([order_line])

    batches.allocate(order)

    in_stock_batch_udpated = attr.evolve(in_stock_batch, quantity=90)
    assert batches.batches[clock.name] == [in_stock_batch_udpated, shipment_batch]


def test_prefers_earlier_batches(now, later, tomorrow):
    spoon = SKU("MINIMALIST-SPOON")

    earliest = create_batch(spoon, 100, eta=now)
    medium = create_batch(spoon, 100, eta=later)
    latest = create_batch(spoon, 100, eta=tomorrow)

    batches = Batches([medium, latest, earliest])

    order_line = OrderLine(sku=spoon, quantity=10)
    order = create_order(lines=[order_line])

    batches.allocate(order)

    updated_earlies = attr.evolve(earliest, quantity=90)
    assert batches.batches[spoon.name] == [updated_earlies, medium, latest]


def test_returns_allocated_batch_ref():
    book = SKU("OLD-BOOK")

    batch = create_batch(book, 100, eta=now)
    batches = Batches([batch])

    order_line = OrderLine(sku=book, quantity=10)
    order = create_order(lines=[order_line])

    references = batches.allocate(order)

    assert references == [batch.reference]
