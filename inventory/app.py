#! /usr/bin/python3

from flask import Flask, g, appcontext_pushed, Response, url_for
from flask import request, redirect
from flask.json import jsonify
import json
from bson.json_util import dumps
from urllib.parse import urlencode

from pymongo import MongoClient, IndexModel, TEXT
from pymongo.errors import ConnectionFailure
from werkzeug.local import LocalProxy

from .data_models import Bin, MyEncoder

app = Flask('inventory')
app.config['LOCAL_MONGO'] = app.debug or app.testing
app.config['SERVER_ROOT'] = 'https://computemachines.com'

# memoize mongo_client
_mongo_client = None
def get_mongo_client():
    global _mongo_client
    if _mongo_client is None:
        if app.config.get('LOCAL_MONGO', False):
            db_host = "localhost"
        else:
            db_host = "mongo"
            # import time
            # time.sleep(20)
        _mongo_client = MongoClient(db_host, 27017)
    return _mongo_client

def get_db():
    if 'db' not in g:
        g.db = get_mongo_client().inventorydb
    return g.db
db = LocalProxy(get_db)

def if_numeric_then_prepend(string, prefix):
    if string.isnumeric():
        return prefix+string
    else:
        return string

# api v0.1.0
@app.route('/api/things', methods=['POST', 'PUT'])
def things_post_put():
    if request.method == 'POST' and request.form['_method'].upper() == 'PUT':
        return things_put()
    elif request.method == 'PUT':
        return things_put()

def things_put():
    form_data = request.form.to_dict()

    thing_label = form_data['thing_label'].upper()
    bin_label = form_data['bin_label'].upper()

    thing_label = if_numeric_then_prepend(thing_label, 'UNIQ')
    bin_label = if_numeric_then_prepend(bin_label, 'BIN')

    db_entry = {
        'label': thing_label,
        'bin': bin_label,
        'name': form_data['thing_name']
    }
    
    db.things.insert_one(db_entry)

    ret = db.things.find_one({'label': thing_label})

    # refresh the page with note
    ret = redirect('/new/thing?' + urlencode({
        'last_inserted': thing_label
    }))
    print(ret)
    return ret

# api v0.1.0
@app.route('/api/things', methods=['GET'])
def things_get():
    all_things = db.things.find()
    return dumps(all_things), 200

# api v0.1.0
@app.route('/api/thing', methods=['POST'])
def thing_post():
    pass

# api v0.1.0
@app.route('/api/thing/<label>', methods=['GET'])
def thing(label):
    label = label.upper()
    label = if_numeric_then_prepend(label, 'UNIQ')
    
    thing = db.things.find_one({'label': label})
    return dumps(thing), 200

# api v0.1.0
@app.route('/api/search', methods=['GET'])
def search_get():
    print('/api/search : {}'.format(request.args))
    query = request.args.get('query')
    results = db.things.find({'$text': {'$search': query}})
    return dumps(results)

# api v1.0.0
@app.route('/api/bins', methods=['GET'])
def bins_get():
    args = request.args
    limit = None
    skip = None
    try:
        limit = int(args.get('limit', 20))
        skip = int(args.get('startingFrom', 0))
    except:
        return "Malformed Request. Possible pagination query parameter constraint violation.", 400

    cursor = db.bins.find()
    cursor.limit(limit)
    cursor.skip(skip)

    bins = [Bin(bsonBin) for bsonBin in cursor]
    
    return json.dumps(bins, cls=MyEncoder)

# api v1.0.0
@app.route('/api/bins', methods=['POST'])
def bins_post():
    bin = Bin(request.json)
    existing = db.bins.find_one({'id': bin._id})
    resp = Response()
    if existing is None:
        db.bins.insert_one(request.json)
        resp.status_code = 201
    else:
        resp.status_code = 409
    resp.headers['Location'] = url_for('bin', label=bin._id)
    return resp

# api v1.0.0
@app.route('/api/bin/<label>', methods=['GET'])
def bin(label):
    existing = db.bins.find_one({"id": label})
    if existing is None:
        return "The bin does not exist", 404
    else:
        bin = BinExtended(existing)
        bin.contents = []
        return bin.toJson(), 200



# @app.teardown_appcontext
# def teardown_db():
#     db = g.pop('db', None)

#     if db is not None:
#         db.close()

if __name__=='__main__':
    app.run(port=8081, debug=True)
