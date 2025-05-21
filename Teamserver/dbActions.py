from rich.console import Console
from datetime     import datetime, timezone

import sqlite3

# probably a sqli in here lol

console = Console()

current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def CreateDB() -> None :
    """Create DB"""

    conn   = sqlite3.connect("Teamserver.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Tasks (
            TaskId  INTEGER PRIMARY KEY NOT NULL,
            Task    TEXT,
            Result  TEXT,
            AgentId TEXT NOT NULL,
            Time    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            Status  TEXT
        );
        ''')

    cursor.execute('''
            CREATE TABLE IF NOT EXISTS Beacons (
            BeaconId TEXT NOT NULL,
            Name     TEXT NOT NULL,
            LastSeen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ''')
    conn.close()

    console.print("[bold green]\nTeamserver database created.\n")

def AddTask( task:str, id:int ) -> None :
    """Add the tasks to the db"""

    conn   = sqlite3.connect("Teamserver.db")
    cursor = conn.cursor()

    conn.execute(f"INSERT INTO Tasks ( Task, AgentId, Status ) VALUES ( ?, ?, ? )", ( task, id, "pending" ) )
    conn.commit()
    conn.close()

    console.print(f"[bold cyan]\nTask added to database\n")

def AddResults( result:str, taskid:int ) -> None :
    """Add and lock results to db"""

    if result == "":
        result = f"No data returned"

    conn   = sqlite3.connect("Teamserver.db")
    cursor = conn.cursor()

    conn.execute(f"UPDATE Tasks SET Result = ?, Status = ?, Time = ? WHERE TaskId = ? ", ( result,"complete", current_time, taskid ) )

    conn.executescript("""
    CREATE TRIGGER IF NOT EXISTS lock_result
    BEFORE UPDATE ON Tasks
    FOR EACH ROW
    WHEN OLD.Result IS NOT NULL AND NEW.Result != OLD.Result
    BEGIN
        SELECT RAISE(ABORT, 'Results are locked and cannot be updated');
    END;
    """)
    
    conn.commit()
    conn.close()

    console.print(f"[bold green]\nResults for Task { taskid } added to database\n")


def GetResults( taskid:int ) -> str :
        """Get results from db"""

        conn   = sqlite3.connect("Teamserver.db")
        cursor = conn.cursor()

        cursor.execute("SELECT TaskId, Result, AgentId, Time FROM Tasks WHERE TaskId = ?", ( taskid, ) )
        results = cursor.fetchall()
        conn.commit()
        conn.close()

        #console.print(f"[bold green]\nResults for { taskid } retrieved from database\n\n")
        return results[0]

def GetTaskId( id:str ) -> int :
        """Get last task from db"""

        conn   = sqlite3.connect("Teamserver.db")
        cursor = conn.cursor()

        cursor.execute("SELECT Taskid FROM Tasks WHERE AgentId = ? ORDER BY TASKID DESC LIMIT 1", ( id, ) )
        id = cursor.fetchall()
        conn.commit()
        conn.close()

        try:
            return id[0][0]
        except IndexError:
            None

def Register( beaconid:str ) -> None :
        """Register beacon to db"""

        name   = f"Agent-{beaconid.split('-')[0]}"
        conn   = sqlite3.connect("Teamserver.db")
        cursor = conn.cursor()

        conn.execute("INSERT INTO Beacons ( BeaconId, Name ) VALUES ( ?, ? )", ( beaconid, name ) )
        conn.commit()
        conn.close()

        console.print(f"\n[bold green]Beacon Registered: {beaconid} \n")

def GetBeacons() -> list[str] :
        """Get Beacons beacons from db"""

        conn   = sqlite3.connect("Teamserver.db")
        cursor = conn.cursor()

        cursor.execute("SELECT BeaconId, Name FROM Beacons")
        beacons = cursor.fetchall()
        conn.commit()
        conn.close()

        return beacons

def UpdateName( agentId:str, name:str ) -> None :
    """Update Agent Name"""

    conn   = sqlite3.connect("Teamserver.db")
    cursor = conn.cursor()

    cursor.execute("UPDATE Beacons SET Name = ? WHERE BeaconId = ?", ( name, agentId ) )
    conn.commit()
    conn.close()

    console.print(f"[bold green]\nAgent {agentId} renamed to {name}\n")

def GetCmd( agentId:str ) -> int :
        """Get cmd from db"""

        conn   = sqlite3.connect("Teamserver.db")
        cursor = conn.cursor()

        cursor.execute("SELECT Task FROM Tasks WHERE Status = 'pending' AND AgentId = ? ORDER BY TaskId DESC LIMIT 1", ( agentId, ) )
        cmd = cursor.fetchall()
        conn.commit()
        conn.close()

        try:
            return cmd[0][0]
        except IndexError:
            None

def Kill( id:str ) -> None :
        """Remove Agent from db"""

        conn   = sqlite3.connect("Teamserver.db")
        cursor = conn.cursor()

        cursor.execute("DELETE FROM Beacons WHERE BeaconId = ? OR Name = ?", ( id,id ) )
        conn.commit()
        conn.close()

        console.print(f"[bold green]\nAgent successfully Killed {id}\n")

def AddLastSeen( id:str ) -> None :
    """Log last seen"""
    conn   = sqlite3.connect("Teamserver.db")
    cursor = conn.cursor()

    cursor.execute("UPDATE Beacons SET LastSeen = ? WHERE BeaconId = ?", ( current_time, id ) )
    conn.commit()
    conn.close()

    #console.print(f"[bold green]\nAgent Timestamp updated {id}\n")

def GetLastSeen() -> list[str] :
        """Get last seen from db"""

        conn   = sqlite3.connect("Teamserver.db")
        cursor = conn.cursor()

        cursor.execute("SELECT BeaconId, LastSeen FROM Beacons")
        lastseen = cursor.fetchall()
        conn.commit()
        conn.close()

        return lastseen
