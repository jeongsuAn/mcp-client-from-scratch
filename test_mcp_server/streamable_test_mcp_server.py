# server_http.py
from fastmcp import FastMCP
mcp = FastMCP("jeongsu_demo")
@mcp.tool()
def current_time() -> str:
    """현재 시간을 반환하는 도구"""
    return "current time: 2050-11-22 15:00"

@mcp.tool()
def get_weather(city: str) -> str:
    """도시의 날씨 정보를 반환하는 도구"""
    return f"weather in {city}: Sunny, 25°C"

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000, path="/mcp")