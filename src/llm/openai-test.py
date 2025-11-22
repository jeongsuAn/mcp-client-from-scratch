from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
# 환경 변수(OPENAI_API_KEY)에서 API 키를 자동으로 읽어옵니다.
# 만약 키를 직접 코드에 입력해야 한다면 client = OpenAI(api_key="YOUR_API_KEY")와 같이 사용합니다.
client = OpenAI()

try:
    # 채팅 응답 생성 요청
    response = client.chat.completions.create(
        model="gpt-5-nano",  # 사용하려는 모델 선택 (예: "gpt-4o", "gpt-3.5-turbo")
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "안녕."}
        ]
    )

    # 응답에서 답변 내용 추출
    answer = response.choices[0].message.content

    print(answer)


except Exception as e:
    print(f"API 요청 중 오류가 발생했습니다: {e}")