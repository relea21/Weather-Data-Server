from flask import Flask, request, Response, jsonify
from pymongo import MongoClient, ASCENDING
from datetime import datetime
import os

app = Flask(__name__)
username = os.environ.get("MONGO_USERNAME", "default_user")
password = os.environ.get("MONGO_PASSWORD", "default_password")
host = os.environ.get("MONGO_HOST", "localhost")
port = os.environ.get("MONGO_PORT", "27017")
database_name = os.environ.get("MONGO_DB", "weather_db")

uri = f"mongodb://{username}:{password}@{host}:{port}/"

client = MongoClient(uri)
db = client[database_name]

def get_next_sequence(name):
    result = db["counters"].find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    return result["seq"]

def initialize_database():
    
    if "Tari" not in db.list_collection_names():
        tari = db["Tari"]
        tari.create_index("nume_tara", unique=True)

    if "Orase" not in db.list_collection_names():
        orase = db["Orase"]
        orase.create_index([("id_tara", ASCENDING), ("nume_oras", ASCENDING)], unique=True)

    if "Temperaturi" not in db.list_collection_names():
        temperaturi = db["Temperaturi"]
        temperaturi.create_index([("id_oras", ASCENDING), ("timestamp", ASCENDING)], unique=True)
    
    db["counters"].update_one({"_id": "Tari"}, {"$setOnInsert": {"seq": 0}}, upsert=True)
    db["counters"].update_one({"_id": "Orase"}, {"$setOnInsert": {"seq": 0}}, upsert=True)
    db["counters"].update_one({"_id": "Temperaturi"}, {"$setOnInsert": {"seq": 0}}, upsert=True)

def delete_country(id):
    countries_collection = db["Tari"]
    cities_collection = db["Orase"]
    temperatures_collection = db["Temperaturi"]

    result = countries_collection.delete_one({"id": id})
    if result.deleted_count == 0:
        return

    city_ids = [city["id"] for city in cities_collection.find({"id_tara": id})]

    cities_collection.delete_many({"id_tara": id})

    if city_ids:
        temperatures_collection.delete_many({"id_oras": {"$in": city_ids}})

def delete_city(id):
    cities_collection = db["Orase"]
    temperatures_collection = db["Temperaturi"]

    result = cities_collection.delete_one({"id": id})
    if result.deleted_count == 0:
        return
    temperatures_collection.delete_many({"id_oras": id})

def delete_temperature(id):
    temperatures_collection = db["Temperaturi"]
    temperatures_collection.delete_one({"id": id})
    
@app.route('/api/countries', methods = ["GET", "POST"])
def get_country():
    if request.method == "GET":
        try:
            countries = list(db["Tari"].find({}, {"_id": 0}))
            for country in countries:
                country["nume"] = country.pop("nume_tara")
                country["lat"] = country.pop("latitudine")
                country["lon"] = country.pop("longitudine")
            return jsonify(countries), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
                
    if request.method == "POST":
        try:
            data = request.json

            if not all(key in data for key in ("nume", "lat", "lon")):
                return jsonify({"error": "Câmpuri lipsă."}), 400

            if not isinstance(data["nume"], str):
                return jsonify({"error": "Câmpul 'nume' trebuie să fie un șir de caractere."}), 400
            try:
                lat = float(data["lat"])
                lon = float(data["lon"])
            except ValueError:
                return jsonify({"error": "Câmpurile 'lat' și 'lon' trebuie să fie numere de tip float."}), 400

            countries_collection = db["Tari"]
            existing_country = countries_collection.find_one({"nume_tara": data["nume"]})
            if existing_country:
                return jsonify({"error": "Țara există deja."}), 409

            id = get_next_sequence("Tari")
            country = {
                "id": id,
                "nume_tara": data["nume"],
                "latitudine": lat,
                "longitudine": lon,
            }
            
            countries_collection.insert_one(country)

            return jsonify({"id": country["id"]}), 201

        except Exception as e:
            return jsonify({"error": f"Eroare internă: {str(e)}"}), 500

@app.route('/api/countries/<int:id>', methods = ["PUT", "DELETE"])
def update_country(id):
    if request.method == "PUT":
        try:
            data = request.json

            if not all(key in data for key in ("id", "nume", "lat", "lon")):
                return jsonify({"error": "Câmpuri lipsă."}), 400

            if id != data["id"]:
                return jsonify({"error": "ID-urile nu coincid."}), 400
            
            if not isinstance(id, int):
                return jsonify({"error": "Câmpul 'id' trebuie să fie un număr întreg."}), 400
            
            if not isinstance(data["nume"], str):
                return jsonify({"error": "Câmpul 'nume' trebuie să fie un șir de caractere."}), 400
            try:
                lat = float(data["lat"])
                lon = float(data["lon"])
            except ValueError:
                return jsonify({"error": "Câmpurile 'lat' și 'lon' trebuie să fie numere de tip float."}), 400

            countries_collection = db["Tari"]
            country = countries_collection.find_one({"id": id})
            if not country:
                return jsonify({"error": "Țara nu există."}), 404
            
            existing_country = countries_collection.find_one({"nume_tara": data["nume"]})
            if existing_country:
                return jsonify({"error": "Țara există deja."}), 409

            country["nume_tara"] = data["nume"]
            country["latitudine"] = lat
            country["longitudine"] = lon

            countries_collection.update_one({"id": id}, {"$set": country})

            return Response(status=200)

        except Exception as e:
            return jsonify({"error": f"Eroare internă: {str(e)}"}), 500

    if request.method == "DELETE":
        try:
            countries_collection = db["Tari"]
            country = countries_collection.find_one({"id": id})   
            if not country:
                return jsonify({"error": "Țara nu a fost găsită."}), 404
            delete_country(id)
            return Response(status=200)

        except Exception as e:
            return jsonify({"error": f"Eroare internă: {str(e)}"}), 500

@app.route('/api/cities', methods = ["GET", "POST"])
def get_city():
    if request.method == "GET":
        try:
            cities = list(db["Orase"].find({}, {"_id": 0}))

            for city in cities:
                city["idTara"] = city.pop("id_tara")
                city["nume"] = city.pop("nume_oras")
                city["lat"] = city.pop("latitudine")
                city["lon"] = city.pop("longitudine")
            
            return jsonify(cities), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if request.method == "POST":
        try:
            data = request.json

            if not all(key in data for key in ("idTara", "nume", "lat", "lon")):
                return jsonify({"error": "Câmpuri lipsă."}), 400

            if not isinstance(data["idTara"], int):
                return jsonify({"error": "Câmpul 'idTara' trebuie să fie un număr întreg."}), 400
            if not isinstance(data["nume"], str):
                return jsonify({"error": "Câmpul 'nume' trebuie să fie un șir de caractere."}), 400
            try:
                lat = float(data["lat"])
                lon = float(data["lon"])
            except ValueError:
                return jsonify({"error": "Câmpurile 'lat' și 'lon' trebuie să fie numere de tip float."}), 400

            countries_collection = db["Tari"]
            country = countries_collection.find_one({"id": data["idTara"]})
            if not country:
                return jsonify({"error": "Țara nu există."}), 404
        
            cities_collection = db["Orase"]
            existing_city = cities_collection.find_one({"id_tara": data["idTara"], "nume_oras": data["nume"]})
            if existing_city:
                return jsonify({"error": "Orașul există deja."}), 409

            id = get_next_sequence("Orase")
            city = {
                "id": id,
                "id_tara": data["idTara"],
                "nume_oras": data["nume"],
                "latitudine": lat,
                "longitudine": lon,
            }
            cities_collection.insert_one(city)

            return jsonify({"id": city["id"]}), 201

        except Exception as e:
            return jsonify({"error": f"Eroare internă: {str(e)}"}), 500

@app.route('/api/cities/<int:id>', methods = ["PUT", "DELETE"])
def update_city(id):
    if request.method == "PUT":
        try:
            data = request.json

            if not all(key in data for key in ("id", "idTara", "nume", "lat", "lon")):
                return jsonify({"error": "Câmpuri lipsă."}), 400

            if id != data["id"]:
                return jsonify({"error": "ID-urile nu coincid."}), 400
            if not isinstance(id, int):
                return jsonify({"error": "Câmpul 'id' trebuie să fie un număr întreg."}), 400
            if not isinstance(data["idTara"], int):
                return jsonify({"error": "Câmpul 'idTara' trebuie să fie un număr întreg."}), 400
            if not isinstance(data["nume"], str):
                return jsonify({"error": "Câmpul 'nume' trebuie să fie un șir de caractere."}), 400
            try:
                lat = float(data["lat"])
                lon = float(data["lon"])
            except ValueError:
                return jsonify({"error": "Câmpurile 'lat' și 'lon' trebuie să fie numere de tip float."}), 400

            countries_collection = db["Tari"]
            country = countries_collection.find_one({"id": data["idTara"]})
            if not country:
                return jsonify({"error": "Țara nu există."}), 404

            cities_collection = db["Orase"]
            city = cities_collection.find_one({"id": id})
            if not city:
                return jsonify({"error": "Orașul nu există."}), 404
            
            existing_city = cities_collection.find_one({"id_tara": data["idTara"], "nume_oras": data["nume"]})
            if existing_city:
                return jsonify({"error": "Orașul există deja."}), 409

            city["id_tara"] = data["idTara"]
            city["nume_oras"] = data["nume"]
            city["latitudine"] = lat
            city["longitudine"] = lon

            cities_collection.update_one({"id": id}, {"$set": city})

            return Response(status=200)

        except Exception as e:
            return jsonify({"error": f"Eroare internă: {str(e)}"}), 500

    if request.method == "DELETE":
        try:
            cities_collection = db["Orase"]
            city = cities_collection.find_one({"id": id})
            if not city:
                return jsonify({"error": "Orașul nu a fost găsit."}), 404
            delete_city(id)
            return Response(status=200)

        except Exception as e:
            return jsonify({"error": f"Eroare internă: {str(e)}"}), 500

@app.route('/api/cities/country/<int:idTara>', methods = ["GET"])
def get_cities_by_country(idTara):
    try:
        countries_collection = db["Tari"]
        country = countries_collection.find_one({"id": idTara})
        if not country:
            return jsonify({"error": "Țara nu există."}), 404

        cities_collection = db["Orase"]
        cities = list(cities_collection.find({"id_tara": idTara}, {"_id": 0}))
        for city in cities:
            city["idTara"] = city.pop("id_tara")
            city["nume"] = city.pop("nume_oras")
            city["lat"] = city.pop("latitudine")
            city["lon"] = city.pop("longitudine")
        return jsonify(cities), 200

    except Exception as e:
        return jsonify({"error": f"Eroare internă: {str(e)}"}), 500

@app.route('/api/temperatures', methods = ["GET", "POST"])
def get_temperature():
    if request.method == "GET":
        try:
            lat = request.args.get('lat', type=float)
            lon = request.args.get('lon', type=float)
            from_date = request.args.get('from')
            until_date = request.args.get('until')

            query = {}

            if lat is not None or lon is not None:
                city_query = {}
                if lat is not None:
                    city_query["latitudine"] = lat
                if lon is not None:
                    city_query["longitudine"] = lon

                cities = list(db["Orase"].find(city_query, {"_id": 0, "id": 1}))
                if not cities:
                    return jsonify({"error": "Nu există orașe pentru coordonatele specificate."}), 404

                city_ids = [city["id"] for city in cities]
                query["id_oras"] = {"$in": city_ids}

            if from_date:
                try:
                    from_date_parsed = datetime.strptime(from_date, "%Y-%m-%d")
                    query.setdefault("timestamp", {})["$gte"] = from_date_parsed
                except ValueError:
                    return jsonify({"error": "Formatul datei nu este AAAA-LL-ZZ"}), 400

            if until_date:
                try:
                    until_date_parsed = datetime.strptime(until_date, "%Y-%m-%d")
                    query.setdefault("timestamp", {})["$lte"] = until_date_parsed
                except ValueError:
                    return jsonify({"error": "Formatul datei nu este AAAA-LL-ZZ"}), 400

            temperatures = list(db["Temperaturi"].find(query, {"_id": 0, "id_oras": 0}))

            return jsonify(temperatures), 200

        except Exception as e:
            return jsonify({"error": f"Eroare internă: {str(e)}"}), 500

    if request.method == "POST":
        try:
            data = request.json
            if not all(key in data for key in ("idOras", "valoare")):
                return jsonify({"error": "Câmpuri lipsă."}), 400

            if not isinstance(data["idOras"], int):
                return jsonify({"error": "Câmpul 'idOras' trebuie să fie un număr întreg."}), 400
            try:    
                float(data["valoare"])
            except ValueError:
                return jsonify({"error": "Valoarea temperaturii nu este un numar."}), 400    

            cities_collection = db["Orase"]
            city = cities_collection.find_one({"id": data["idOras"]})
            if not city:
                return jsonify({"error": "Orașul nu există."}), 404
            date_time = datetime.now()
            temperatures_collection = db["Temperaturi"]
            existing_temperature = temperatures_collection.find_one({"id_oras": data["idOras"], "timestamp": date_time})
            if existing_temperature:
                return jsonify({"error": "Temperatura există deja."}), 409
            id = get_next_sequence("Temperaturi")
            temperature = {
                "id": id,
                "valoare": float(data["valoare"]),
                "timestamp": date_time,
                "id_oras": data["idOras"],
            }
            
            temperatures_collection.insert_one(temperature)

            return jsonify({"id": temperature["id"]}), 201

        except Exception as e:
            return jsonify({"error": f"Eroare internă: {str(e)}"}), 500

@app.route('/api/temperatures/<int:id>', methods = ["PUT", "DELETE"])
def update_temperature(id):
    if request.method == "PUT":
        try:
            data = request.json
            if not all(key in data for key in ("id", "idOras", "valoare")):
                return jsonify({"error": "Câmpuri lipsă."}), 400

            if id != data["id"]:
                return jsonify({"error": "ID-urile nu coincid."}), 400
            
            if not isinstance(data["idOras"], int):
                return jsonify({"error": "Câmpul 'idOras' trebuie să fie un număr întreg."}), 400
            try:    
                float(data["valoare"])
            except ValueError:
                return jsonify({"error": "Valoarea temperaturii nu este un numar."}), 400

            cities_collection = db["Orase"]
            city = cities_collection.find_one({"id": data["idOras"]})
            if not city:
                return jsonify({"error": "Orașul nu există."}), 404

            temperatures_collection = db["Temperaturi"]
            temperature = temperatures_collection.find_one({"id": id})
            if not temperature:
                return jsonify({"error": "Temperatura nu există."}), 404

            existing_temperature = temperatures_collection.find_one({"id_oras": data["idOras"], "timestamp": temperature["timestamp"]})
            if existing_temperature:
                return jsonify({"error": "Temperatura există deja."}), 409

            temperature["id_oras"] = data["idOras"]
            temperature["valoare"] = float(data["valoare"])

            temperatures_collection.update_one({"id": id}, {"$set": temperature})

            return Response(status=200)

        except Exception as e:
            return jsonify({"error": f"Eroare internă: {str(e)}"}), 500

    if request.method == "DELETE":
        try:
            temperatures_collection = db["Temperaturi"]
            temperature = temperatures_collection.find_one({"id": id})
            if not temperature:
                return jsonify({"error": "Temperatura nu a fost găsită."}), 404
            delete_temperature(id)
            return Response(status=200)

        except Exception as e:
            return jsonify({"error": f"Eroare internă: {str(e)}"}), 500

@app.route('/api/temperatures/cities/<int:id_oras>', methods = ["GET"])
def get_temperatures_by_city(id_oras):
    try:
        from_date = request.args.get('from')
        until_date = request.args.get('until')

        query = {"id_oras": id_oras}

        if from_date:
            try:
                from_date_parsed = datetime.strptime(from_date, "%Y-%m-%d")
                query.setdefault("timestamp", {})["$gte"] = from_date_parsed
            except ValueError:
                return jsonify({"error": "Formatul datei nu este AAAA-LL-ZZ"}), 400

        if until_date:
            try:
                until_date_parsed = datetime.strptime(until_date, "%Y-%m-%d")
                query.setdefault("timestamp", {})["$lte"] = until_date_parsed
            except ValueError:
                return jsonify({"error": "Formatul datei nu este AAAA-LL-ZZ"}), 400

        temperatures = list(db["Temperaturi"].find(query, {"_id": 0, "id_oras": 0}))

        return jsonify(temperatures), 200

    except Exception as e:
        return jsonify({"error": f"Eroare internă: {str(e)}"}), 500

@app.route('/api/temperatures/countries/<int:id_tara>', methods=["GET"])
def get_temperatures_by_country(id_tara):
    try:

        cities_collection = db["Orase"]
        cities = list(cities_collection.find({"id_tara": id_tara}, {"_id": 0}))
        if not cities:
            return jsonify({"error": "Țara nu există sau nu are orașe asociate."}), 404

        city_ids = [city["id"] for city in cities]

        from_date = request.args.get('from')
        until_date = request.args.get('until')
        query = {"id_oras": {"$in": city_ids}}

        if from_date:
            try:
                from_date_parsed = datetime.strptime(from_date, "%Y-%m-%d")
                query.setdefault("timestamp", {})["$gte"] = from_date_parsed
            except ValueError:
                return jsonify({"error": "Formatul datei nu este AAAA-LL-ZZ"}), 400

        if until_date:
            try:
                until_date_parsed = datetime.strptime(until_date, "%Y-%m-%d")
                query.setdefault("timestamp", {})["$lt"] = until_date_parsed
            except ValueError:
                return jsonify({"error": "Formatul datei nu este AAAA-LL-ZZ"}), 400

        temperatures_collection = db["Temperaturi"]
        temperatures = list(temperatures_collection.find(query, {"_id": 0, "id_oras": 0}))

        return jsonify(temperatures), 200

    except Exception as e:
        return jsonify({"error": f"Eroare internă: {str(e)}"}), 500
if __name__ == "__main__":
    initialize_database()
    app.run(host="0.0.0.0", port=8080)