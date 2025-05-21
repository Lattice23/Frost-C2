from requests.exceptions import ConnectionError
from frost               import FrostShell
from time                import sleep

import threading
import argparse
import requests
import random
import json

def StartClient() -> None : 
    """
    Listen for agent results
    """
    success = False

    # Wait 10 secs to connect to server
    with frost.console.status(f"[bold cyan]Connecting to Teamserver... {frost.BASEURL}", spinner="dots"):
        for _ in range( 10 ) :
            try :
                 beacons_results = requests.get(f"{frost.BASEURL}/beacons?sync=true").json()
                 if ( beacons_results != None ):
                    beacons = beacons_results["Agents"]
                    for id, name in beacons:
                        frost.agents[id] = name
                        frost.known_agents.add(id)
                 success = True
                 break
            except Exception :
                    sleep(1)
        else:
            pass

    if not success:
        frost.console.print(f"[bold red]Failed to connect teamserver!")
        frost.do_exit( 1 )

    TimeStampThread = threading.Thread( target=GetTimestamps).start()
    RegisterThread  = threading.Thread( target=GetRegistered).start()

    # Catch keyboard interrupts
    try:
        frost.cmdloop()
    except KeyboardInterrupt:
        try:
            frost.console.print("[bold red]\n\ninput Ctrl-c once more to exit")
            catch = input()
            if ( catch ) or ( catch == "" ) :
                frost.intro = ""
                frost.cmdloop()
        except KeyboardInterrupt:
            frost.do_exit( 1 )


def GetRegistered() -> None :
    """
    Check for new registered frost.agents
    """
    while True:
        try:
            # refresh registered frost.agents from sever
            beacons_results = requests.get(f"{frost.BASEURL}/beacons?sync=true").json()

            if ( beacons_results != None ) :
                beacons = beacons_results["Agents"]

                for ( id, name ) in beacons:
                     if id not in frost.known_agents:
                         frost.console.print(f"[bold cyan] Registered Agent: { id }")
                         if name == f"Agent-{id.split('-')[0]}" :
                             frost.agents[id] = name
                             frost.known_agents.add(id)
                         else:
                             frost.agents[id] = name

            sleep(random.uniform(2, 5))
        except requests.exceptions.ConnectionError as error :
                frost.console.print(f"[bold red]Failed connection to teamserver!")
                frost.do_exit( 1 )

def GetTimestamps():
    """
    Get beacon frost.timestamps from teamserver
    """
    while True:
        try:
            timestamp = requests.get(f"{frost.BASEURL}/ping?sync=true").json()

            for id, stamp in timestamp:
                frost.timestamps[id] = stamp

            sleep(random.uniform(2, 5))
        except requests.exceptions.ConnectionError as error :
                pass

if ( __name__ == "__main__" ) :

    parser = argparse.ArgumentParser(description='Frost Client')

    parser.add_argument( '-s', '--server', help='Teamserver IP'  , default='127.0.0.1')
    parser.add_argument( '-p', '--port',   help='Teamserver port', default='5000')

    SERVER  = parser.parse_args().server
    PORT    = parser.parse_args().port

    frost = FrostShell( SERVER, PORT )

    StartClient()

