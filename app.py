import uuid
import os
import requests
from flask import Flask, request, json, jsonify, session, redirect, url_for, render_template, make_response
import msal
import app_config
from flask_cors import CORS, cross_origin
from flaskext.mysql import MySQL
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity 
import datetime


app = Flask(__name__, template_folder="templates")
app.config.from_object(app_config)
CORS(app)
mysql = MySQL(app)
jwt = JWTManager(app)
app.config['DEBUG'] = True





@app.route('/api/test', methods=["GET"])
@cross_origin()
@jwt_required
def index():
    user = get_jwt_identity()

    return {"name":user}

@app.route('/api/getResponse', methods=["POST"])
@cross_origin()
def repsonse():
    req = request.data
    return req

# Create token for user on logon
@app.route('/api/createToken', methods=["POST"])
def createToken():
    if request.is_json:
        req = request.get_json()
        
        # IF no user return
        if req.get('user') == "None":
            
            return {"user": "No user specified"}, 400
        #Check if user exist in db
        user = req.get('user')
        conn = mysql.connect()
        cur = conn.cursor()
        cur.execute("select * from Bruker where Brukernavn = %(user)s", {'user': user})
        
        if cur.rowcount != 1:
            return {"denied":"No user found"}, 400
        #User exist set token and return    
        expires = datetime.timedelta(hours=1)
        expires_at = (datetime.datetime.today() + expires).strftime('%Y-%m-%dT%H:%M:%S')
        access_token = create_access_token(identity=str(user), expires_delta=expires)
        return {'token': access_token,
                'expires': expires_at},200
    else:

        return make_response(jsonify({"message": "Request body must be JSON"}), 400)


@app.route('/api/customers', methods=["GET"])

def customers():
    conn = mysql.connect()

    cur = conn.cursor()
    cur.execute("Select * from Customers")
    all_customers = cur.fetchall()

    x = []

    for customer in all_customers:
        x.append({"id":customer[0], 
                  "firstName":customer[1],
                  "lastName":customer[2],
                  "email":customer[3],
                  "phone":customer[4],
                  "city":customer[5]})
    return jsonify(x)

# Get all blandekort from db

@app.route('/api/blandekort', methods=["GET"])
@jwt_required
def blandekort():

    conn = mysql.connect()
    cur = conn.cursor()
    cur.execute('select * from Blandekort where ATC_VNR="N01A X03-3.2"')
    all_blandekort = cur.fetchall()
    o = []
    for x in all_blandekort:
        o.append({"ATC_VNR":x[0], 
                  "ATC_kode":x[1],
                  "Bruker_ID":x[2],
                  "VersjonsNr":x[3],
                  "Dato":x[4],
                  "Internt_Godjent":x[5],
                  "Eksternt_Godjent":x[6],
                  "Aktivt":x[7],
                  "Bruker_ID_A":x[8],
                  "Blandekortdata":x[9],
                  "Fortynning": x[10]})
   
    return jsonify(o), 200

@app.route('/json', methods=["POST"])
def json_example():
    if request.is_json:   
        req = request.get_json()
       
        response_body = {
            "message": "JSON recieved!!",
            "sender": req.get("name")
        }

        res = make_response(jsonify(response_body), 200)

        return res

    else:

        return make_response(jsonify({"message": "Request body must be JSON"}), 400)


if __name__ == '__main__':
    app.run()