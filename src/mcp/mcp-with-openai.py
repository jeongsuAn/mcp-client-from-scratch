import json
import requests
import uuid
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MCP_URL = "http://localhost:8000/mcp"

# https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle
init_payload = {
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-06-18",
    "capabilities": {
      "roots": {
        "listChanged": True
      },
      "sampling": {},
      "elicitation": {}
    },
    "clientInfo": {
      "name": "ExampleClient",
      "title": "Example Client Display Name",
      "version": "1.0.0"
    }
  }
}

custom_headers = {
    "Accept": "application/json, text/event-stream"
}

resp = requests.post(MCP_URL, json=init_payload, headers=custom_headers)

print(resp.content.decode())
# --- 응답 정보 ---
# Status Code: 200
# Response Headers: 
#   {'date': 'Wed, 12 Nov 2025 13:15:07 GMT', 
#    'server': 'uvicorn', 
#    'cache-control': 'no-cache, no-transform',
#    'connection': 'keep-alive', 
#    'content-type': 'text/event-stream', 
#    'mcp-session-id': '2d27d9b84afc45cd983e256b2772dab0', 
#    'x-accel-buffering': 'no', 
#    'Transfer-Encoding': 'chunked'
#   }
# Response Text : event: message
# data: 
#   {"jsonrpc":"2.0",
#    "id":1,
#    "result":{
#       "protocolVersion":"2025-06-18",
#       "capabilities":{
#           "experimental":{},
#           "prompts":{"listChanged":true},
#           "resources":{"subscribe":false,"listChanged":true},
#           "tools":{"listChanged":true}
#         },
#         "serverInfo":{
#           "name":"jeongsu_demo",
#           "version":"2.13.0.2"
#         }
#       }
#     }
#   }


# 정상적인 작업을 시작할 준비가 되었다는 알림을 보내야한다. 
session_id = resp.headers.get("mcp-session-id")
custom_headers["MCP-Session-ID"] = session_id
ready_payload = {
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
resp = requests.post(MCP_URL, json=ready_payload, headers=custom_headers) # custom_headers는 항상 있어야한다.
print("\nready response:")
print(resp.status_code) 
print(resp.headers)  
print(resp.content.decode()) 

# ready response:
# 202
# {'date': 'Wed, 12 Nov 2025 13:38:31 GMT', 'server': 'uvicorn', 'content-type': 'application/json', 'mcp-session-id': '9def9a00b1bf4f3bad7a43b070bb3f5b', 'content-length': '0'}


# 툴 리스트 조회 
# https://modelcontextprotocol.io/specification/2025-06-18/server/tools
tools_payload = {
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {
    "cursor": "optional-cursor-value"
  }
}
resp = requests.post(MCP_URL, json=tools_payload, headers=custom_headers)
print("\ntools response:")
print(resp.status_code)  # 200
print(resp.headers)
print(resp.content.decode())  # 툴 리스트 정보

raw_text = resp.content.decode()
print(raw_text)  # 응답 원본 (event: message\ndata: ...)

# --- 💡 여기부터 수정됨 💡 ---

json_string = None
# 1. 응답을 줄 단위로 분리
for line in raw_text.splitlines():
    # 2. "data: "로 시작하는 줄을 찾음
    if line.startswith("data: "):
        # 3. "data: " 부분을 제외한 나머지(순수 JSON 문자열)를 추출
        json_string = line[len("data: "):].strip()
        break

tools_list = []
# 4. JSON 문자열을 성공적으로 찾은 경우에만 파싱
if json_string:
    try:
        # 5. 'json()'이 아닌 'json.loads()'로 파싱
        data = json.loads(json_string)
        tools_list = data.get("result", {}).get("tools", [])
    except json.JSONDecodeError as e:
        print(f"JSON 파싱 에러: {e}")
        print(f"파싱 시도한 문자열: {json_string}")
else:
    print("응답에서 'data:' 라인을 찾을 수 없습니다.")

# --- 💡 수정 끝 💡 ---

print("\n--- 추출된 도구 목록 ---")
if tools_list:
    for tool in tools_list:
        print(tool.get("name"), " : ", tool.get("description"))
else:
    print("도구를 찾지 못했습니다.")

# 200
# {'date': 'Wed, 12 Nov 2025 14:02:06 GMT', 'server': 'uvicorn', 'cache-control': 'no-cache, no-transform', 'connection': 'keep-alive', 'content-type': 'text/event-stream', 'mcp-session-id': '1c5611eabf06439a9c178b4c7ba13a4f', 'x-accel-buffering': 'no', 'Transfer-Encoding': 'chunked'}
# event: message
# data: {"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"current_time","inputSchema":{"properties":{},"type":"object"},"outputSchema":{"properties":{"result":{"type":"string"}},"required":["result"],"type":"object","x-fastmcp-wrap-result":true},"_meta":{"_fastmcp":{"tags":[]}}}]}}


client = OpenAI()

def convert_mcp_tool_to_openai(mcp_tool: dict) -> dict:
    """MCP 도구 명세를 OpenAI 'function' 도구 명세로 변환합니다."""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.get("name"),
            "description": mcp_tool.get("description", ""), # description이 없다면 빈 문자열
            "parameters": mcp_tool.get("inputSchema", {"type": "object", "properties": {}})
        }
    }

# 2. MCP 서버에 실제 'tools/call'을 요청하는 헬퍼 함수
# https://modelcontextprotocol.io/specification/2025-06-18/server/tools
def call_mcp_tool(session_headers: dict, tool_name: str, tool_args: dict) -> any:
    """OpenAI가 요청한 도구를 실제 MCP 서버에 'tools/call'로 실행합니다."""
    print(f"--- MCP 서버에 'tools/call' 요청: {tool_name}({tool_args}) ---")
    
    mcp_tool_call_id = str(uuid.uuid4())
    payload = {
        "jsonrpc": "2.0",
        "id": mcp_tool_call_id, # 이 요청을 위한 새 ID
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": tool_args,
        }
    }
    
    try:
        resp = requests.post(MCP_URL, json=payload, headers=session_headers)
        resp.raise_for_status() # HTTP 에러 체크

        raw_text = resp.content.decode()
        print(f"MCP 'tools/call' 응답 상태 코드: {resp.status_code}")
        print(f"MCP 'tools/call' 응답 원본:\n{raw_text}")
        
        
        for line in raw_text.splitlines():
            if line.startswith("data: "):
                json_string = line[len("data: "):].strip()
                
                # data: 라인 뒤에 내용이 없는 경우 스킵
                if not json_string:
                    continue
                    
                try:
                    data = json.loads(json_string)
                except json.JSONDecodeError as e:
                    print(f"JSON 파싱 오류: {e}, 라인: {json_string}")
                    continue # 다음 라인 시도

                # 1. 최우선: MCP가 'error'를 반환했는지 확인
                if "error" in data:
                    print(f"MCP 도구 실행 에러: {data['error']}")
                    return f"Error: {data['error'].get('message', '알 수 없는 오류')}"

                # 2. 'result' 키가 있고, 그것이 딕셔너리인지 확인
                if "result" in data and isinstance(data.get("result"), dict):
                    mcp_result_data = data["result"]
                    
                    # 3. 새로운 표준 경로 (structuredContent.result) 확인
                    if ("structuredContent" in mcp_result_data and 
                        isinstance(mcp_result_data.get("structuredContent"), dict) and 
                        "result" in mcp_result_data["structuredContent"]):
                        
                        mcp_result = mcp_result_data["structuredContent"]["result"]
                        print(f"MCP 도구 실행 결과: {mcp_result}")
                        return mcp_result # 성공! 결과 반환

                    # 4. 기존 경로 (result.result)도 하위 호환성을 위해 확인
                    if "result" in mcp_result_data:
                        mcp_result = mcp_result_data["result"]
                        print(f"MCP 도구 실행 결과 (대체 경로): {mcp_result}")
                        return mcp_result # 성공! 결과 반환
                
                # 1, 2, 3, 4 모두 해당하지 않으면 유효한 응답 구조가 아님
                # (다음 data: 라인을 위해 루프 계속)

        # for 루프를 모두 돌았는데 유효한 data를 못찾음
        return "Error: MCP에서 유효한 'data:' 응답 또는 결과 필드를 찾지 못했습니다."
    except requests.RequestException as e:
        print(f"MCP 'tools/call' 요청 실패: {e}")
        return f"Error: {e}"
    except json.JSONDecodeError as e:
        print(f"MCP 'tools/call' 응답 파싱 실패: {e}")
        return "Error: Failed to parse MCP response"


# --- 💡 메인 로직 💡 ---

print("\n--- OpenAI Tool Call 시작 ---")

# 3. MCP 도구 목록을 OpenAI 형식으로 변환
openai_tools = [convert_mcp_tool_to_openai(tool) for tool in tools_list]
print(f"OpenAI에 {len(openai_tools)}개의 도구를 전달합니다: {[t['function']['name'] for t in openai_tools]}")

# 4. 사용자 질문 정의 (도구를 사용하도록 유도)
user_prompt = "서울 날씨 어떻게 돼?"
print(f"\n사용자 질문: {user_prompt}")

messages = [
    {"role": "user", "content": user_prompt}
]

# 5. 첫 번째 OpenAI 호출 (도구 목록과 함께)
try:
    response = client.chat.completions.create(
        model="gpt-5-nano", 
        messages=messages,
        tools=openai_tools,
        tool_choice="auto"  # OpenAI가 도구 사용을 결정
    )

    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    # 6. OpenAI가 도구 사용을 요청했는지 확인
    if tool_calls:
        print("\nOpenAI가 도구 호출을 요청했습니다.")
        print("tool_calls : ", tool_calls)
        # 어시스턴트의 응답(도구 호출 요청)을 대화 기록에 추가
        messages.append(response_message)

        tool_outputs = [] # 도구 실행 결과를 담을 리스트

        # 7. 요청된 모든 도구 실행
        for tool_call in tool_calls:
            
            tool_name = tool_call.function.name
            # tool_call.function.arguments는 JSON *문자열*이므로 파싱 필요
            print("도구 호출 요청:", tool_name, tool_call.function.arguments)
            tool_args = json.loads(tool_call.function.arguments) 
            oa_tool_call_id = tool_call.id # OpenAI가 부여한 이 호출의 고유 ID
 
            # 위에서 만든 헬퍼 함수로 MCP 서버에 실제 도구 실행 요청
            mcp_result = call_mcp_tool(
                session_headers=custom_headers,
                tool_name=tool_name,
                tool_args=tool_args
            )

            # 8. 도구 실행 결과를 OpenAI가 요구하는 형식으로 추가
            tool_outputs.append({
                "tool_call_id": oa_tool_call_id,
                "role": "tool",
                "content": json.dumps({"result": mcp_result}) # 결과를 JSON 문자열로 전달
            })

        # 9. 두 번째 OpenAI 호출 (도구 결과와 함께)
        print("도구 실행 결과를 OpenAI에 전달하여 최종 답변을 생성합니다.")
        
        # 대화 기록에 도구 결과(들) 추가
        messages.extend(tool_outputs)
        print("최종 메시지 기록:", messages)

        final_response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=messages # 전체 대화 기록 (User -> Assistant(tool) -> Tool(result))
        )

        final_answer = final_response.choices[0].message.content
        print("\n--- 🤖 최종 답변 ---")
        print(final_answer)

    else:
        # OpenAI가 도구를 사용하지 않고 바로 답변한 경우
        print("\n--- 🤖 최종 답변 (도구 미사용) ---")
        print(response_message.content)

except Exception as e:
    print(f"OpenAI API 오류 발생: {e}")