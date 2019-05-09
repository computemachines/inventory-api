import pytest
from hypothesis import given, example, settings, Verbosity, reproduce_failure, assume
import hypothesis.strategies as strat
import tests.data_models_strategies as my_strat

from inventory.app import app as inventory_flask_app
from inventory.app import get_mongo_client, db
from inventory.data_models import Bin, MyEncoder, Uniq, Batch, Sku

from contextlib import contextmanager
from flask import appcontext_pushed, g, request_started
import json

def subscriber(sender):
    g.db = get_mongo_client().testing
request_started.connect(subscriber, inventory_flask_app)

def init_db():
    get_mongo_client().testing.bin.drop()
    get_mongo_client().testing.uniq.drop()
    get_mongo_client().testing.sku.drop()
    get_mongo_client().testing.batch.drop()

    
@pytest.fixture
def client():
    inventory_flask_app.testing = True
    inventory_flask_app.config['LOCAL_MONGO'] = True
    init_db()
    yield inventory_flask_app.test_client()
    #close app


def test_empty_db(client):
    with client:
        resp = client.get("/api/bins")
        assert b"[]" == resp.data

        assert b"[]" == client.get("/api/units").data

        assert g.db.bin.count_documents({}) == 0
        assert g.db.uniq.count_documents({}) == 0
        assert g.db.sku.count_documents({}) == 0
        assert g.db.batch.count_documents({}) == 0

@strat.composite
def strat_bins(draw, id=None, props=None, contents=None):
    id = id or f"BIN{draw(strat.integers(0, 10)):08d}"
    props = props or draw(my_strat.json)
    contents = contents or draw(strat.just([]) | strat.none())
    return Bin(id=id, props=props, contents=contents)


@strat.composite
def strat_uniqs(draw, id=None, bin_id=None):
    id = id or f"UNIQ{draw(strat.integers(0, 10)):07d}"
    bin_id = bin_id or f"BIN{draw(strat.integers(0, 10)):08d}"
    return Uniq(id=id, bin_id=bin_id)

@strat.composite
def strat_skus(draw, id=None, owned_codes=None, name=None):
    id = id or f"SKU{draw(strat.integers(0, 10)):08d}"
    owned_codes = owned_codes or draw(strat.lists(strat.text("abc")))
    name = draw(strat.text("ABC"))
    return Sku(id=id, owned_codes=owned_codes, name=name)

@strat.composite
def strat_batches(draw, id=None, sku_id=None):
    id = id or f"BAT{draw(strat.integers(0, 10)):08d}"
    sku_id = sku_id or f"SKU{draw(strat.integers(0, 100)):08d}"
    return Batch(id=id, sku_id=sku_id)

# import pdb; pdb.set_trace()

@given(bins=strat.lists(strat_bins(), max_size=10))
def test_post_bins(client, bins):
    init_db()
    submitted_bins = []
    for bin in bins:
        resp = client.post("/api/bins", json=bin.to_json())
        if bin.id not in submitted_bins:
            assert resp.status_code == 201
            submitted_bins.append(bin.id)
        else:
            assert resp.status_code == 409        

            
@example(units=strat.lists(strat_uniqs(), max_size=10, min_size=1).example(),
         bins=[])
@given(units=strat.lists(strat_uniqs(), max_size=10, min_size=1),
       bins=strat.lists(strat_bins(props={}), min_size=10, max_size=20))
def test_post_uniq(client, units, bins):
    assume(not bins or not set(unit.bin_id for unit in units)
                  .isdisjoint(bin.id for bin in bins))
    init_db()

    for bin in bins:
        client.post("/api/bins", json=bin.to_json())
    bin_ids = [bin.id for bin in bins]
    
    submitted_units = []
    for unit in units:
        resp = client.post("/api/units/uniqs", json=unit.to_json())
        if unit.id in submitted_units:
            assert resp.status_code == 409
        elif unit.bin_id not in bin_ids:
            assert resp.status_code == 404
        else:
            assert resp.status_code == 201
            submitted_units.append(unit.id)

@given(units=strat.lists(strat_skus()),
       bins=strat.lists(strat_bins(), max_size=10))
def test_post_sku(client, units, bins):
    
    init_db()
    
    for bin in bins:
        client.post("/api/bins", json=bin.to_json())
    bin_ids = [bin.id for bin in bins]

    submitted_units = []
    for unit in units:
        resp = client.post("/api/units/skus", json=unit.to_json())
        if unit.id in submitted_units:
            assert resp.status_code == 409
        elif set().bin_ids:
            assert resp.status_code == 404
        else:
            assert resp.status_code == 201
            submitted_units.append(unit.id)

@given(units=strat.lists(strat_batches()))
def test_post_batch(client, units):
    init_db()
    submitted_units = []
    for unit in units:
        resp = client.post("/api/units/batches", json=unit.to_json())
        if unit.id not in submitted_units:
            assert resp.status_code == 201
            submitted_units.append(unit.id)
        else:
            assert resp.status_code == 409
