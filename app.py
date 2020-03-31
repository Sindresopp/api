import uuid
import os
import requests
from functools import wraps
from flask import Flask, request, json, jsonify, session, redirect, url_for, render_template, make_response
import msal
import app_config
from flask_cors import CORS, cross_origin
from flaskext.mysql import MySQL
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt_claims, verify_jwt_in_request, get_raw_jwt
import datetime
from models.classes import UserObject
from wrappers import admin_required
from functions import isAdmin


app = Flask(__name__)
app.config.from_object(app_config)  
CORS(app)
mysql = MySQL(app)
jwt = JWTManager(app)


@jwt.user_claims_loader
def add_claim_to_access_token(user):
    return {'roles': user.roles}

@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.username

@app.route('/api/test', methods=["GET"])
@cross_origin()
@jwt_required
def index():
    ret = get_raw_jwt()
    print (ret['exp'])
   # user = get_jwt_identity()

    return jsonify(ret),200

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
        
        #IF no user return
        if req.get('user') == "None":
            
            return {"user": "No user specified"}, 400

        #Check if user exist in db
        userCheck = req.get('user')

        conn = mysql.connect()
        cur = conn.cursor()
        cur.execute("select Brukernavn, IF(isAdmin,%(true)s, %(false)s)isAdmin from Bruker where Brukernavn = %(user)s", {'user': userCheck, 'true': "true", 'false': "false"})
        if cur.rowcount != 1:
            return {"denied":"No user found"}, 400

       # Check if admin
        res = cur.fetchall()
        print(res)
        if isAdmin(res[0][1]):
            user = UserObject(username=userCheck, roles='admin')
        else:
            user = UserObject(username=userCheck, roles='user')   

        
        expires_at = (datetime.datetime.today() + app_config.JWT_ACCESS_TOKEN_EXPIRES).strftime('%Y-%m-%dT%H:%M:%S')
        access_token = create_access_token(identity=user)
        return {'token': access_token,
                'expires': expires_at},200
    else:

        return make_response(jsonify({"message": "Request body must be JSON"}), 400)


@app.route('/api/customers', methods=["GET"])
@admin_required
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

# Get a specific card 

@app.route('/api/blandekort', methods=["GET"])
@jwt_required
def blandekort():
    atc_vnr = request.args['atc_vnr']
    
    conn = mysql.connect()
    cur = conn.cursor()
    query = """select b.ATC_VNR, b.ATC_kode,v.Virkestfoffnavn, b.VersjonsNr, date_format(b.dato, %(date_format)s), b.Blandekortdata, 
               b.Fortynning, b.Bruker_ID,b.Bruker_ID_A, b.Internt_Godkjent,b.Eksternt_Godkjent,b.aktivt  From Blandekort as b 
               inner join Virkestoff as v on b.ATC_kode=v.ATC_kode 
               where ATC_VNR = %(card)s;"""
    values = {"date_format":"%d.%m.%Y" ,"card": atc_vnr}
    cur.execute(query, values)
    all_blandekort = cur.fetchall()
    
    o = []
    for x in all_blandekort:
        o.append({"ATC_VNR":x[0], 
                  "ATC_kode":x[1],
                  "Virkestoff":x[2],
                  "VersjonsNr":x[3],
                  "Dato":x[4],
                  "Blandekortdata":x[5],
                  "Fortynning":x[6],
                  "Bruker_ID": x[7],
                  "Bruker_Aktivert":x[8],
                  "Internt_Godkjent":x[9],
                  "Eksternt_Godkjent":x[10],
                  "Aktivt":x[11]})
    return jsonify(o), 200

#Get acitve cards

@app.route('/api/aktiveBlandekort', methods=['GET'])
@jwt_required
def getActive():

    conn = mysql.connect()
    cur = conn.cursor()
    query = """ select b.ATC_kode, v.Virkestfoffnavn, date_format(b.dato, %(string)s), b.VersjonsNr,  group_concat(p.Handelsnavn) as Handelsnavn from Blandekort as b 
                inner join Virkestoff as v on v.ATC_kode = b.ATC_kode 
                inner join Preparat as p on p.ATC_kode=b.ATC_kode 
                where b.Aktivt = %(true)s
                group by v.Virkestfoffnavn,p.ATC_kode, b.Dato, b.VersjonsNr"""
    values = {"string":"%d.%m.%Y","true": True}
    cur.execute(query, values)
    res = cur.fetchall()
    o = []
    for x in res:
        a = x[4].split(',')
        o.append({
            "ATC_kode":x[0],
            "Virkestoff":x[1],
            "Dato":x[2],
            "VersjonsNr":x[3],
            "Handelsnavn": a
        })
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