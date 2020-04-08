from flask import jsonify

def isAdmin(res):
    if res == 'true':
        return True
    
    return False

def addStotte(req, mysql):
    table = req.get('tabell')
    input = req.get('input')

    conn = mysql.connect()
    cur = conn.cursor()

    #Check if value exists

    checkQuery ="SELECT * FROM "
    checkQuery += table
    checkQuery +=" WHERE Beh_navn = %(beholder)s"
    checkValue = {"beholder": input}
    cur.execute(checkQuery, checkValue)

    if cur.rowcount != 0:
        return jsonify("Innhold finnes alt i tabellen"), 403

    query = "INSERT INTO "
    query += table
    query += " VALUES (%(id)s,%(value)s)"
    values = {"id": None, "value": input}
    cur.execute(query, values)
    conn.commit()
    cur.execute(checkQuery,checkValue)
    if(cur.rowcount == 1):
        return jsonify("Suksess"), 201
    cur.close() 
    return jsonify("Fikk ike lagt til innholdet") ,204

def addVirkestoff(req, mysql):
    table = req.get('tabell')
    data = req.get('data')

    conn = mysql.connect()
    cur = conn.cursor()

    checkQuery ="SELECT * FROM "
    checkQuery += table
    checkQuery +=" WHERE ATC_kode = %(atckode)s or VirkeStoffNavn = %(virkestoff)s"
    checkValue = {"atckode": data.get('atckode'), "virkestoff": data.get('virkestoffNavn') }
    cur.execute(checkQuery, checkValue)
    
    if(cur.rowcount > 0):
        return jsonify("ERROR:" + data.get('virkestoffNavn') +" eller " +data.get('atckode')+" finnes allerede i tabellen " +  table), 403

    query = "INSERT INTO "
    query += table
    query += " VALUES (%(atckode)s,%(virkestoff)s)"
    values = {"atckode": data.get('atckode'), "virkestoff": data.get('virkestoffNavn') }
    cur.execute(query, values)
    conn.commit()
    cur.execute(checkQuery,checkValue)
    if(cur.rowcount == 1):
        return jsonify("Suksess"), 201
    cur.close() 
    
    return jsonify("Fikk ikke lagt til innholdet"), 204



def addPreparat(req, mysql):
    
    table = req.get('tabell')
    data = req.get('data')

    conn = mysql.connect()
    cur = conn.cursor()

    checkQuery ="SELECT * FROM "
    checkQuery += table
    checkQuery +=" WHERE ATC_kode = %(atckode)s and Handelsnavn = %(handelsnavn)s and Produsent =%(produsent)s"
    checkValue = {"atckode": data.get('atckode'), "handelsnavn": data.get('handelsnavn'), "produsent": data.get('produsent') }
    cur.execute(checkQuery, checkValue)
    
    if(cur.rowcount > 0):
        return jsonify("Preparatet "+ data.get('preparat') + "fra "+ data.get('produsent')+ " tilhørende atckode " +data.get('atckode')+ " finnes allerede"), 403

    query = "INSERT INTO "
    query += table
    query += " VALUES (%(id)s,%(handelsnavn)s,%(produsent)s,%(atckode)s)"
    values = {"id":None,"atckode": data.get('atckode'), "handelsnavn": data.get('handelsnavn'), "produsent": data.get('produsent')   }
    cur.execute(query, values)
    conn.commit()
    
    cur.execute(checkQuery,checkValue)
    if(cur.rowcount == 1):
        return jsonify("Suksess"), 201
    cur.close() 
    
    return jsonify("Fikk ikke lagt til innholdet"), 204

def addLenke(req, mysql):
    table = req.get('tabell')
    data = req.get('data')

    conn = mysql.connect()
    cur = conn.cursor()

    checkQuery ="SELECT * FROM "
    checkQuery += table
    checkQuery +=" WHERE Navn = %(navn)s and URL = %(URL)s "
    checkValue = {"navn": data.get('navn'), "URL": data.get('URL')}
    cur.execute(checkQuery, checkValue)
    
    if(cur.rowcount > 0):
        return jsonify("Lenken " + data.get('navn') + " med URL: "+ data.get('URL')+ " finnes allerede"), 403

    query = "INSERT INTO "
    query += table
    query += " VALUES (%(id)s,%(navn)s,%(URL)s)"
    values = {"id":None,"navn": data.get('navn'), "URL": data.get('URL')}
    cur.execute(query, values)
    conn.commit()
    
    cur.execute(checkQuery,checkValue)
    if(cur.rowcount == 1):
        return jsonify("Suksess"), 201
    cur.close() 
    
    return jsonify("Fikk ikke lagt til innholdet"), 204
    

def addReferanse(req, mysql):
    table = req.get('tabell')
    data = req.get('data')

    conn = mysql.connect()
    cur = conn.cursor()

    checkQuery ="SELECT * FROM "
    checkQuery += table
    checkQuery +=" WHERE Navn = %(navn)s and URL = %(URL)s "
    checkValue = {"navn": data.get('navn'), "URL": data.get('URL')}
    cur.execute(checkQuery, checkValue)
    
    if(cur.rowcount > 0):
        return jsonify("Referansen "+ data.get('navn')+ " med URL: "+ data.get('URL')+ " finnes allerede"), 403

    query = "INSERT INTO "
    query += table
    query += " VALUES (%(id)s,%(navn)s,%(URL)s)"
    values = {"id":None,"navn": data.get('navn'), "URL": data.get('URL')}
    cur.execute(query, values)
    conn.commit()
    
    cur.execute(checkQuery,checkValue)
    if(cur.rowcount == 1):
        return jsonify("Suksess"), 201
    cur.close() 
    
    return jsonify("Fikk ikke lagt til innholdet"), 204

def addLMU(req, mysql):
    
    table = req.get('tabell')
    data = req.get('data')

    conn = mysql.connect()
    cur = conn.cursor()

    checkQuery ="SELECT * FROM "
    checkQuery += table
    checkQuery +=" WHERE Sted = %(sted)s and Region = %(region)s and Sykehus = %(sykehus)s"
    checkValue = {"sted": data.get('sted'), "region": data.get('region'), "sykehus": data.get('sykehus')}
    cur.execute(checkQuery, checkValue)
    
    if(cur.rowcount > 0):
        return jsonify("LMU i "+data.get('sted')+ " er allerede lagt til."), 403

    query = "INSERT INTO "
    query += table
    query += " VALUES (%(id)s,%(sted)s,%(region)s,%(sykehus)s)"
    values = {"id":None,"sted": data.get('sted'), "region": data.get('region'), "sykehus": data.get('sykehus')}
    cur.execute(query, values)
    conn.commit()
    
    cur.execute(checkQuery,checkValue)
    if(cur.rowcount == 1):
        return jsonify("Suksess"), 201
    cur.close() 
    
    return jsonify("Fikk ikke lagt til innholdet"), 204