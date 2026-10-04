
import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

from tools import TOOLS

load_dotenv()

model = ChatGoogleGenerativeAI(
    model=os.getenv("MODEL_NAME"),
    
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0,
)

SYSTEM_PROMPT = """
Bạn là AI Agent hỗ trợ đặt vé máy bay.

Quy tắc:
- Chỉ sử dụng dữ liệu từ các tool được cung cấp.
- Không tự bịa chuyến bay, giá vé hoặc mã đặt chỗ.
- Phải tìm chuyến bay trước khi kiểm tra ghế.
- Không được đặt vé nếu chưa có xác nhận rõ ràng của người dùng.
- Nếu thiếu thông tin, hãy hỏi người dùng.
- Nếu tool báo lỗi, hãy thông báo lỗi chính xác.
- Các tool chỉ mô phỏng đặt vé, không phải hệ thống thật.
"""

react_agent = create_agent(
    model=model,
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
)


def run_react(user_input: str):
    result = react_agent.invoke(
        {
            "messages": [
                {"role": "user", "content": user_input}
            ]
        },
        config={"recursion_limit": 15},
    )

    return result["messages"][-1].content