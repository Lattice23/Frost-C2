cmake_minimum_required(VERSION 3.10)
project(agent)

set(CMAKE_CXX_STANDARD 17)

set(CMAKE_EXE_LINKER_FLAGS "-static")

add_executable(agent agent.cpp)

target_link_libraries(agent winhttp)

