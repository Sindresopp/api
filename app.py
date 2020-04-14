import uuid
import simplejson as jsonfun
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


#Conect to DB and returns cursor
def connectDB():
    conn = mysql.connect()
    cur = conn.cursor()
    return cur, conn

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

#Hent alle virkstoff som ikke har vært på høring
@app.route('/api/virkestoff', methods=["GET"])
@jwt_required
def virkestoff():
    conn = mysql.connect()
    cur = conn.cursor()
    
    query = """ select v.ATC_kode, v.VirkeStoffNavn from Virkestoff as v 
                left join Blandekort as b on b.ATC_kode = v.ATC_kode
                where b.ATC_kode is null; """

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

#
# Spørringer for blandekort
#

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
    return jsonfun.dumps(o), 200

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
    values = {"string":"%Y.%m.%d","true": True}
    cur.execute(query, values)
    res = cur.fetchall()
    if not res:
        return jsonify("No content"), 204
    o = []
    for x in res:
        
        a = x[5].split(',')
        o.append({
            "ATC_kode":x[0],
            "Virkestoff":x[1],
            "Dato": x[2],
            "VersjonsNr":x[3],
            "ATC_VNR": x[4],
            "Handelsnavn": a
        })
    response = jsonfun.dumps(o)
    return response, 200

#Get revisions of a blandekort

@app.route('/api/blandekort/revisjoner', methods=['GET'])
def getRevision():

    conn = mysql.connect()
    cur = conn.cursor()

    query = """SELECT b.ATC_kode, date_format(b.dato, %(string)s), b.VersjonsNr, b.ATC_VNR, v.VirkeStoffNavn FROM Blandekort as b 
               inner join Virkestoff as v on v.ATC_kode = b.ATC_kode
               WHERE (b.Aktivt = %(bool)s or b.Aktivt is null) AND b.Eksternt_Godkjent = %(god)s"""
    values = {"string": "%d.%m.%Y","bool": False, "god":True }

    cur.execute(query,values)

    res = cur.fetchall()
    if not res:
        return jsonify("no contetn"), 204
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
        return jsonify("no content"),204
    o = []
    
    for x in res:
        o.append({
            "ATC_kode": x[0],
            "Dato": x[1],
            "VersjonsNr": x[2],
            "ATC_VNR": x[3],
            "Virkestoff": x[4]
        })

    return jsonfun.dumps(o),200

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

#Update godkjenne blandekort 
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

        if not userID:
            return jsonify('Fant ingen bruker'), 403

        dateNow = datetime.datetime.now()

        

        ATC_VNR = req.get('ATC_VNR')

        query = "UPDATE Godkjent SET "

        if not req.get('ForsteGod'):
            query += " Bruker_ID2 = %(user)s, Dato_2 = Date(%(date)s) WHERE ATC_VNR = %(atcvnr)s;"
            queryValues = {"user": userID, "date":dateNow.strftime('%Y-%m-%dT%H:%M:%S'), "atcvnr": ATC_VNR }

            cur.execute(query, queryValues)
            conn.commit()
            return jsonify("Godkjent tabell oppdatert"), 200

        if req.get('ForsteGod'):
            query += " Bruker_ID3 = %(user)s, Dato_3 = Date(%(date)s) where ATC_VNR = %(atcvnr)s "
            queryValues = {"user": userID, "date":dateNow.strftime('%Y-%m-%dT%H:%M:%S'), "atcvnr": ATC_VNR }
            
            cur.execute( query, queryValues)
            conn.commit()

            updateCardQuery = " UPDATE Blandekort SET Internt_Godkjent = %(bool)s WHERE ATC_VNR = %(atcvnr)s "
            updateCardValues = {"bool": True, "atcvnr": ATC_VNR}
            cur.execute(updateCardQuery,updateCardValues)
            conn.commit()
            return jsonify("Blandekort ferdig godkjent"),200

    return jsonify("Forespørselen er feil"), 400


#Make new blandekort
@app.route('/api/blandekort/opprett', methods=['POST'])
@admin_required
def makeNewBlandekort():
    if request.is_json:

        conn = mysql.connect()
        cur = conn.cursor()
        user = get_jwt_identity()
        userID = getUserIDByName(user, cur)

        now = datetime.datetime.now()
        req = request.get_json()        
        blandekortData = req.get('Blandekortdata')
       
        jsondum = json.dumps(blandekortData)
        query ="INSERT INTO Blandekort values (%(atcvnr)s,%(atckode)s,%(brukerID)s,%(VersjonsNr)s,Date(%(date)s),%(internt)s,%(eksternt)s,%(aktivt)s,%(brukerID_A)s,%(blandekortdata)s,%(fortynning)s)"
        
        queryValues = {
            "atcvnr": req.get('ATC_VNR'),
            "atckode": req.get('ATC_kode'),
            "brukerID": userID,
            "VersjonsNr": req.get('VersjonsNr'),
            "date": now.strftime('%Y-%m-%dT%H:%M:%S'),
            "internt": req.get('Internt_Godkjent'),
            "eksternt": req.get('Eksternt_Godkjent'),
            "aktivt": req.get('aktivt'),
            "brukerID_A": None,
            "blandekortdata": jsondum,
            "fortynning": None
            }
        
        cur.execute(query, queryValues)
        conn.commit()
        
        gQuery = "INSERT INTO Godkjent values (%(id)s,null,null,null,null,null,null,%(atcvnr)s)"
        gQueryValues = {
            "id":None,
            "atcvnr": req.get('ATC_VNR')
        }
        cur.execute(gQuery,gQueryValues)
        conn.commit()

        return jsonify("Success"),201

#Publiser blandekort 
@app.route('/api/blandekort/publiser', methods=['GET','POST'])
@jwt_required
def publiserBlandekort():
    if request.method == 'GET':

       
        cur = connectDB()[0]

        query = """ select v.VirkeStoffNavn, b.ATC_kode, date_format(g.Dato_3,%(datestring)s), b.VersjonsNr, b.ATC_VNR from Blandekort as b
                    inner join Virkestoff as v on v.ATC_kode = b.ATC_kode
                    inner join Godkjent as g on g.ATC_VNR = b.ATC_VNR
                    where b.Aktivt = %(aktivt)s and b.Internt_Godkjent = %(internt)s and b.Eksternt_godkjent = %(eksternt)s;"""
        queryValues = {"datestring": '%Y.%m.%d', "aktivt": False, "internt":True, "eksternt":True}

        cur.execute(query, queryValues)
        res = cur.fetchall()

        if not res:
            return jsonify('no content'),204

        o = []

        for x in res:
            o.append({
                "Virkestoff": x[0],
                "ATC_kode": x[1],
                "Dato_godkjent": x[2],
                "VersjonsNr": x[3],
                "ATC_VNR": x[4]
            })    

        return jsonify(o),200



    if request.method == 'POST':

        if not request.is_json:
            return jsonify("Provide json"), 400
        conn = mysql.connect()
        cur = conn.cursor()
        req = request.get_json()
        atcvnr = req.get('atcvnr')
        userID = getUserIDByName(get_jwt_identity(),cur)
        query = "UPDATE Blandekort SET Aktivt = %(bool)s, Bruker_ID_A = %(userid)s where ATC_VNR = %(atcvnr)s"
        queryValues = {"bool": True, "userid": userID, "atcvnr": atcvnr}

        cur.execute(query, queryValues)
        conn.commit()

        return jsonify("Blandekort publisert"),201

#Info om valgte publiser kort

@app.route('/api/blandekort/infopub', methods=['GET'])
@jwt_required
def getInfoCard():

    atcvnr = request.args.get('atcvnr', None)
    atckode = request.args.get('atckode', None)

    if not atcvnr or not atckode:
        return jsonify("Must specify args"),400
    cur = connectDB()[0]
    query = """     select et.Utarbeider, et.Godkjenner1, et.Godkjenner2, ar.VersjonsNr from
            (select b1.Brukernavn as Utarbeider ,b2.Brukernavn as Godkjenner1 ,b3.Brukernavn as Godkjenner2, ATC_kode  from Godkjent g
            inner join Bruker b1 on b1.Bruker_ID = g.Bruker_ID1
            inner join Bruker b2 on b2.Bruker_ID = g.Bruker_ID2
            inner join Bruker b3 on b3.Bruker_ID = g.Bruker_ID3
            left join Blandekort b on b.ATC_VNR = g.ATC_VNR
            where g.ATC_VNR = %(atcvnr)s) as et  
            left join
            (select VersjonsNr, ATC_kode from Blandekort b where b.Aktivt= true and b.ATC_kode = %(atckode)s) as ar
            on (et.ATC_kode = ar.ATC_kode); """
    queryValues = {"atcvnr": atcvnr, "atckode": atckode}

    cur.execute(query, queryValues)
    
    res = cur.fetchall()
    if not res:
        return jsonify('no content'),204
    
    o= []
    for x in res:
        o.append({
            "Utarbeider": x[0],
            "Godkjenner1": x[1],
            "Godkjenner2": x[2],
            "VersjonsNr": x[3]
        })

    print(res)
    return jsonify(o), 200

#
# Spørringer for tabeller 
#

#Get tables
@app.route('/api/tabell', methods=['GET'])
@jwt_required
def getStotteTables():

    conn = mysql.connect()
    cur = conn.cursor()
    tables = ["Beholder", 
              "Maaleenhet", 
              "Form",
              "Fraser_Stamloesning",
              "Stamloesning_tillegg", 
              "Valg_vfortynning", 
              "Loesning_vfortynning", 
              "L_VF_tillegg", 
              "Fraser_vfortynning", 
              "Vaeske_vfortynning", 
              "Admin_tid", 
              "Admin_tid_tillegg", 
              "Admin_tilleggfrase",
              "Valg_holdbarhet",
              "Y_vaesker",
              "Bivirkninger",
              "Monitorering"
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


#
# Spørringer for høring
#

@app.route('/api/hoering/kort', methods=['GET'])
@jwt_required
def getCardHoering():

    conn = mysql.connect()
    cur = conn.cursor()

    query = """ select b.ATC_kode, date_format(b.Dato,%(date_string)s), b.VersjonsNr, b.ATC_VNR, v.VirkeStoffNavn
                from Blandekort as b 
                inner join Virkestoff as v on v.ATC_kode = b.ATC_kode 
                left join Hoering as h on h.ATC_kode = b.ATC_kode 
                where b.Eksternt_godkjent = %(eksternt)s and b.Internt_Godkjent = %(internt)s and h.ATC_kode is %(value)s and b.VersjonsNr < 1;"""

    queryValues = {"date_string": '%d.%m.%y', "eksternt": False, "internt": True, "value": None}

    cur.execute(query, queryValues)
    
    res = cur.fetchall()

    o = []

    for x in res:
        o.append({
            "ATC_kode": x[0],
            "Dato": x[1],
            "VersjonsNr": x[2],
            "ATC_VNR": x[3],
            "Virkestoff": x[4],
            "Status": "Kan sendes"
        })

    return jsonify(o),200

@app.route('/api/hoering/lmuer', methods=['GET'])
@jwt_required
def getLMUer():

    cur = connectDB()[0]

    query = "SELECT * FROM LMUer"
    cur.execute(query)

    res = cur.fetchall()
    o = []
    for x in res:
        o.append({
            "ID": x[0],
            "Sted": x[1],
            "Region": x[2],
            "Sykehus": x[3]
        })
    return jsonify(o),200
    

@app.route('/api/hoering/sendkort', methods=['POST'])
@admin_required
def sendCardHoering():
    if request.is_json:

        req = request.get_json()
        
        conn = mysql.connect()
        cur = conn.cursor()

        date = datetime.datetime.now()
        query = "INSERT INTO Hoering values (%(id)s, Date(%(date)s), %(godkjent)s, %(lmuID)s, %(atckode)s, %(brukerID)s)"

        queryValues = {"id": None, "date": date.strftime('%Y-%m-%dT%H:%M:%S'), "godkjent": None, "lmuID": req.get('lmuID'), "atckode": req.get('atckode'), "brukerID":None}

        cur.execute(query, queryValues)
        
        conn.commit() 

        return jsonify("Høring lagt til"),201
    return jsonify("Feil format"), 400

# Hent kort som er sendt på høring
@app.route('/api/hoering/sendtekort', methods=['GET'])
@jwt_required
def getSendtCards():

    cur = connectDB()[0]

    query= """  select date_format(h.Dato_sendt,%(date_string)s), b.ATC_kode, date_format(b.dato,%(date_string)s), v.VirkeStoffNavn, l.Sykehus,l.Region, b.ATC_VNR, b.VersjonsNr From Hoering as h
                inner join Blandekort as b on b.ATC_kode = h.ATC_kode
                inner join Virkestoff as v on v.ATC_kode = h.ATC_kode
                inner join LMUer as l on l.LMU_ID = h.LMU_ID
                where Dato_godkjent is null and b.Eksternt_godkjent = false;"""
    queryValues = {"date_string": '%d.%m.%y'}

    cur.execute(query,queryValues)
    res = cur.fetchall()

    o = []

    for x in res:
        o.append({
            "Dato_sendt": x[0],
            "Dato_revidert": x[2],
            "ATC_kode": x[1],
            "Virkestoff": x[3],
            "Mottaker": x[5]+" ved "+ x[4],
            "ATC_VNR": x[6],
            "VersjonsNr": x[7]
        })
    return jsonify(o), 200

@app.route('/api/hoering/sendtekort', methods=['POST'])
@jwt_required
def setCardApproved():
    if not request.is_json:
        return 400
    conn = mysql.connect()
    cur = conn.cursor()
    req = request.get_json()
    userID = getUserIDByName(get_jwt_identity(),cur)

    
    query = "UPDATE Hoering SET Dato_godkjent = Date(%(date)s), BrukerID_Godkjent = %(userID)s where ATC_kode = %(atckode)s;"
    queryValues = {"date": datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), "userID":userID, "atckode": req.get('atckode')}

    cur.execute(query, queryValues)
    conn.commit()
    queryG = "UPDATE Blandekort set Eksternt_Godkjent = %(bool)s, VersjonsNr = %(versjon)s where ATC_VNR = %(atcvnr)s"
    queryValuesG = {"bool": True, "versjon":1.0, "atcvnr": req.get('atcvnr')}

    cur.execute(queryG,queryValuesG)
    conn.commit()
    return jsonify("Blandekort godkjent"), 200


#Status høringer
@app.route('/api/hoering/status', methods=['GET'])
@jwt_required
def getStatusHoering():

    cur = connectDB()[0]

    query = """ select v.VirkeStoffNavn, h.ATC_kode, date_format(h.Dato_godkjent,%(date)s), l.Sykehus, l.Region, h.Dato_sendt from Hoering as h
                inner join Virkestoff as v on v.ATC_kode = h.ATC_kode
                inner join LMUer as l on l.LMU_ID = h.LMU_ID;"""
    queryValues = {"date":'%Y.%m.%d'}
    cur.execute(query, queryValues)

    res = cur.fetchall()

    o = []
    print(res)
    for x in res:
        if x[2] is None:
            status = "På høring"

        else:
            status = "Godkjent"
        
        o.append({
            "Virkestoff": x[0],
            "ATC_kode": x[1],
            "Dato_godkjent": x[2],
            "Mottaker": x[4]+" ved "+ x[3],
            "Status": status
        })

    return jsonify(o), 200

#OVersikt LMU

@app.route('/api/hoering/LMUoversikt', methods=['GET'])
@jwt_required
def getOversiktLMU():

    cur = connectDB()[0]

    query = """ select distinct l.Sykehus, l.Region, date_format(max(Dato_sendt),%(datestring)s) , count(h.Dato_sendt)
                from Hoering as h
                inner join LMUer as l on l.LMU_ID = h.LMU_ID
                group by l.Sykehus, l.Region;"""
    queryValues = {"datestring": '%Y.%m.%d'}
    cur.execute(query, queryValues)
    res = cur.fetchall()

    o = []
    for x in res:
        o.append({
            "LMU": x[0],
            "Region": x[1],
            "Siste": x[2],
            "Antall": x[3]
        })
    return jsonify(o),200

# #Add item to table
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


#Hent lenker
@app.route('/api/lenker', methods=['GET'])
@jwt_required
def getLenker():

    cur = connectDB()[0]

    query = "SELECT Navn, URL FROM Lenker"
    cur.execute(query)
    res = cur.fetchall()
    if not res:
        return jsonify("no content"), 204
    o = []
    for x in res:
        o.append({
            "Navn": x[0],
            "URL": x[1]
        })
    return jsonify(o), 200  
if __name__ == '__main__':
    app.run()