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
from functions import isAdmin, addStotte, addVirkestoff, addPreparat, addLenke, addReferanse, addLMU, getUserIDByName


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

@app.route('/',methods=['GET'])
@jwt_required
def checkID():
    identity = get_jwt_identity()
    role = get_jwt_claims()
    return jsonify(identity, role)


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
        cur.execute("select Brukernavn, IF(isAdmin,%(true)s, %(false)s)isAdmin from Bruker where azure_ID = %(user)s", {'user': userCheck, 'true': "true", 'false': "false"})
        if cur.rowcount != 1:
            return {"denied":"No user found"}, 400

       # Check if admin
        res = cur.fetchall()
        print(res)
        if isAdmin(res[0][1]):
            user = UserObject(username=res[0][0], roles='admin')
        else:
            user = UserObject(username=res[0][0], roles='user')   

        
        expires_at = (datetime.datetime.today() + app_config.JWT_ACCESS_TOKEN_EXPIRES).strftime('%Y-%m-%dT%H:%M:%S')
        access_token = create_access_token(identity=user)
        return {'token': access_token,
                'expires': expires_at},200
    else:

        return make_response(jsonify({"message": "Request body must be JSON"}), 400)

#Get all virkestoff
@app.route('/api/virkestoff', methods=["GET"])
@jwt_required
def virkestoff():
    conn = mysql.connect()
    cur = conn.cursor()
    
    query = "SELECT * FROM Virkestoff ORDER BY VirkeStoffNavn"

    cur.execute(query)

    res = cur.fetchall()
    cur.close()
    o = []
    for x in res:
        o.append({
            "ATC_kode":x[0],
            "Virkestoff":x[1]
        })
    return jsonify(o), 200

# Get preparat by atccode
@app.route('/api/preparat', methods=['GET'])
@jwt_required
def preparatByATC():
    atc_kode = request.args['atc_kode']

    if (len(atc_kode) == 8):

        conn = mysql.connect()
        cur = conn.cursor()

        query = "SELECT * FROM Preparat WHERE ATC_kode = %(atc_kode)s"

        values = {"atc_kode": atc_kode}
        
        cur.execute(query, values)

        res = cur.fetchall()

        if not res:
            return "Det finnes ingen preparat på denne atc koden.",204
        
        o = []

        for x in res:
            o.append({
                "id": x[0],
                "Handelsnavn": x[1],
                "Produsent": x[2],
                "ATC_kode": x[3]
            })

        return jsonify(o), 200
    
    return jsonify("ATC koden er feil"), 400

# Get a specific card 

@app.route('/api/blandekort', methods=["GET"])
@jwt_required
def blandekort():
    atc_vnr = request.args['atc_vnr']
    
    conn = mysql.connect()
    cur = conn.cursor()
    query = """select b.ATC_VNR, b.ATC_kode,v.VirkeStoffNavn, b.VersjonsNr, date_format(b.dato, %(date_format)s), b.Blandekortdata, 
               b.Fortynning, b.Bruker_ID,b.Bruker_ID_A, b.Internt_Godkjent,b.Eksternt_Godkjent,b.aktivt  From Blandekort as b 
               inner join Virkestoff as v on b.ATC_kode=v.ATC_kode 
               where ATC_VNR = %(card)s;"""
    values = {"date_format":"%d.%m.%Y" ,"card": atc_vnr}
    cur.execute(query, values)
    all_blandekort = cur.fetchall()

    if not all_blandekort:
        return "Det finnes ingen blandekort med denne id'en", 204
    
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
    query = """ select b.ATC_kode, v.VirkeStoffNavn, date_format(b.dato, %(string)s), b.VersjonsNr, b.ATC_VNR,  group_concat(p.Handelsnavn) as Handelsnavn from Blandekort as b 
                inner join Virkestoff as v on v.ATC_kode = b.ATC_kode 
                inner join Preparat as p on p.ATC_kode=b.ATC_kode 
                where b.Aktivt = %(true)s
                group by v.VirkeStoffNavn,p.ATC_kode,b.ATC_VNR, b.Dato, b.VersjonsNr"""
    values = {"string":"%d.%m.%Y","true": True}
    cur.execute(query, values)
    res = cur.fetchall()
    o = []
    for x in res:
        a = x[5].split(',')
        o.append({
            "ATC_kode":x[0],
            "Virkestoff":x[1],
            "Dato":x[2],
            "VersjonsNr":x[3],
            "ATC_VNR": x[4],
            "Handelsnavn": a
        })
    return jsonify(o), 200

#Get revisions of a blandekort

@app.route('/api/blandekort/revisjoner/<atc_kode>', methods=['GET'])
def getRevision(atc_kode):

    conn = mysql.connect()
    cur = conn.cursor()

    query = """SELECT b.ATC_kode, date_format(b.dato, %(string)s), b.VersjonsNr, b.ATC_VNR, v.VirkeStoffNavn FROM Blandekort as b 
               inner join Virkestoff as v on v.ATC_kode = b.ATC_kode
               WHERE b.Aktivt = %(bool)s AND b.Eksternt_Godkjent = %(god)s AND b.ATC_kode = %(atckode)s"""
    values = {"string": "%d.%m.%Y","bool": False, "god":True ,"atckode":atc_kode}

    cur.execute(query,values)

    res = cur.fetchall()

    o = []
    
    for x in res:
        o.append({
            "ATC_kode": x[0],
            "Dato": x[1],
            "VersjonsNr": x[2],
            "ATC_VNR": x[3],
            "Virkestoff": x[4]
        })

    return jsonify(o), 200

#Send blandekort to approvel

@app.route('/api/blandekort/tilgodkjenning', methods=['POST'])
@admin_required
def sendToGodkjenning():
    if request.is_json:
        user = get_jwt_identity()
        req = request.get_json()
        fetchUserQuery = "SELECT Bruker_ID FROM Bruker WHERE Brukernavn = %(user)s"
        conn = mysql.connect()
        cur = conn.cursor()
        cur.execute (fetchUserQuery, {"user": user})

        userRes = cur.fetchone()

        if not userRes:
            return jsonify("User dosent exist"), 403
       
        sendQuery = "UPDATE Godkjent set Bruker_ID1 = %(user)s, Dato_1 = Date(%(date)s) where ATC_VNR = %(atcvnr)s"
        now = datetime.datetime.now()
        
        sendValues = {"user": userRes[0], "date": now.strftime('%Y-%m-%dT%H:%M:%S'), "atcvnr": req.get('ATC_VNR')}
        cur.execute(sendQuery, sendValues)
        conn.commit()
        cur.close()

        return jsonify("Tabell oppdatert"), 201
    return jsonify("Shit"), 400

#Get all utkast
@app.route('/api/blandekort/utkast', methods=['GET'])
def getUtkast():

    conn = mysql.connect()
    cur = conn.cursor()

    query = """SELECT b.ATC_kode, date_format(b.dato, %(string)s), b.VersjonsNr, b.ATC_VNR, v.VirkeStoffNavn FROM Blandekort as b 
               inner join Godkjent as g on g.ATC_VNR = b.ATC_VNR
               inner join Virkestoff as v on v.ATC_kode = b.ATC_kode
               where g.Bruker_ID1 IS NULL"""

    values = {"string": "%d.%m.%Y"}
    
    cur.execute(query, values)

    res = cur.fetchall()

    if not res:
        return 204
    o = []
    
    for x in res:
        o.append({
            "ATC_kode": x[0],
            "Dato": x[1],
            "VersjonsNr": x[2],
            "ATC_VNR": x[3],
            "Virkestoff": x[4]
        })

    return jsonify(o),200

#Get all cards for godkjenning
@app.route('/api/blandekort/godkjenne', methods=['GET'])
@jwt_required
def getCardForGodkjenning():

    conn = mysql.connect()
    cur = conn.cursor()

    query = """select  b.ATC_kode, date_format(g.Dato_1, %(string)s), b.VersjonsNr, b.ATC_VNR, v.VirkeStoffNavn, br.Brukernavn, bru.Brukernavn  from Blandekort as b 
               inner join Godkjent as g on g.ATC_VNR = b.ATC_VNR 
               inner join Virkestoff as v on v.ATC_kode=b.ATC_kode
               inner join Bruker as br on br.Bruker_ID = g.Bruker_ID1
               left join Bruker as bru on bru.Bruker_ID = g.Bruker_ID2 and g.Bruker_ID2 is not null
               where g.Bruker_ID1 is not null and (g.Bruker_ID2 is null or g.Bruker_ID3 is null);"""
    values = {"string": "%d.%m.%Y"}
    cur.execute(query, values)

    res = cur.fetchall()

    if not res:
        return jsonify("Ingen kort til godkjenning"), 204
    
    o = []

    for x in res:
        o.append({
            "ATC_kode": x[0],
            "DatoSendt": x[1],
            "VersjonsNr": x[2],
            "ATC_VNR": x[3],
            "Virkestoff": x[4],
            "SendtAv": x[5],
            "ForsteGod": x[6]
        })
    return jsonify(o), 200

#Update blandekort 
@app.route('/api/blandekort/updateGodkjenne', methods=['POST'])
@jwt_required
def updateGodkjenn():
    if request.is_json:

        user = get_jwt_identity()
        conn = mysql.connect()
        cur = conn.cursor()
        req = request.get_json()

        if (user == req.get('SendtAv')) or (user == req.get('ForsteGod')):
            return jsonify('Brukeren har alt godkjent dette kortet'), 403
        
        userID = getUserIDByName(user, cur)
        dateNow = datetime.datetime.now()

        

        ATC_VNR = req.get('ATC_VNR')

        query = "UPDATE Godkjent SET "

        if not req.get('ForsteGod'):
            query += " Bruker_ID2 = %(user)s, Dato_2 = Date(%(date)s) WHERE ATC_VNR = %(atcvnr)s;"
            queryValues = {"user": userID, "date":dateNow.strftime('%Y-%m-%dT%H:%M:%S'), "atcvnr": ATC_VNR }

            cur.execute(query, queryValues)
            conn.commit()
        return jsonify("Godkjent tabell oppdatert"), 200
    return jsonify("Hei det funker ikke")

#Get tables
@app.route('/api/tabell', methods=['GET'])
@admin_required
def getStotteTables():

    conn = mysql.connect()
    cur = conn.cursor()
    tables = ["Beholder", 
              "Maaleenhet", 
              "Form",
              "Fraser_Stamloesning", 
              "Valg_vfortynning", 
              "Loesning_vfortynning", 
              "L_VF_tillegg", 
              "Fraser_vfortynning", 
              "Vaeske_vfortynning", 
              "Admin_tid", 
              "Admin_tid_tillegg", 
              "Admin_tilleggfrase",
              "Valg_holdbarhet",
              "Y_vaesker"
              ]

    o = []

    for x in tables:
      query = "SELECT * FROM " + x
      cur.execute(query)
      res = cur.fetchall()
      o.append({x:res})


    return jsonify(o), 200


#Add to table
@app.route('/api/tabell/<sporring>', methods=['POST'])
@admin_required
def addToTable(sporring):
    print(request.get_data())
    if request.is_json:
        req = request.get_json()

        return globals()[sporring](req, mysql)


#Add item to table
@app.route('/add/innhold/<table>', methods=['POST'])
def leggTil(table):
    tabell = table
    req = request.get_json()

    conn = mysql.connect()
    cur = conn.cursor()

    query = "Insert into "
    query += tabell
    query += " values (%(id)s,%(innhold)s)"
    value = ""

    for a in req:
        value = {"id":None,"innhold": a}
        cur.execute(query, value)
        conn.commit()

    return "done"



if __name__ == '__main__':
    app.run()