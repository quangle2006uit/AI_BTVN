import json
import os
import re
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI

# Import từ các file của bạn
from tools import search_flights, check_seat, book_flight, get_booking
from harness import FlightRequest, check_completion, check_permission, handoff

PLANNER_PROMPT = """
Bạn là Planner của hệ thống đặt vé máy bay.
Hãy lập kế hoạch dạng JSON gồm danh sách steps.
Mỗi step chỉ được dùng một trong các action:
- search_flights
- check_seat
- validate_passenger
- request_confirmation
- book_flight
- get_booking

Thứ tự bắt buộc để đặt vé là:
1. search_flights
2. check_seat
3. validate_passenger (để xác nhận đã có đủ thông tin hành khách)
4. request_confirmation (để yêu cầu người dùng đồng ý trước khi đặt)
5. book_flight

Chỉ trả về JSON:
{
    "steps": [
        {
            "action": "...",
            "reason": "..."
        }
    ]
}
"""

ALLOWED_ACTIONS = {"search_flights", "check_seat", "validate_passenger", "request_confirmation", "book_flight", "get_booking"}

model = ChatGoogleGenerativeAI(
    model=os.getenv("MODEL_NAME", "gemini-1.5-flash"),
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0,
    model_kwargs={"response_mime_type": "application/json"},
)

def get_response_text(response) -> str:
    content = response.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        result = [item if isinstance(item, str) else item.get("text", "") for item in content]
        return "".join(result).strip()
    return str(content).strip()

def clean_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[len("```json"):].strip()
    elif raw.startswith("```"):
        raw = raw[len("```"):].strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()
    return raw

def create_plan(user_input: str) -> dict:
    response = model.invoke([("system", PLANNER_PROMPT), ("human", user_input)])
    raw = clean_json(get_response_text(response))
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner không trả về JSON hợp lệ:\n{raw}") from e
    
    if "steps" not in plan or not isinstance(plan["steps"], list):
        raise ValueError("Planner không trả về 'steps' hợp lệ.")
        
    for step in plan["steps"]:
        if step.get("action") not in ALLOWED_ACTIONS:
            raise ValueError(f"Action không hợp lệ: {step.get('action')}")
            
    return plan

def extract_flight_data(user_input: str) -> dict:
    data = {}
    
    # Trích xuất tuyến bay
    route_match = re.search(r"\b([A-Za-z]{3})\s*(?:đến|->|to|-)\s*([A-Za-z]{3})\b", user_input, re.IGNORECASE)
    if route_match:
        data["from_city"] = route_match.group(1).upper()
        data["to_city"] = route_match.group(2).upper()
        
    # Trích xuất ngày
    date_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", user_input)
    if date_match:
        try:
            data["date"] = datetime(int(date_match.group(3)), int(date_match.group(2)), int(date_match.group(1))).date().isoformat()
        except ValueError:
            pass
            
    # Trích xuất mã chuyến bay (VD: VN101)
    flight_match = re.search(r"\b([A-Z]{2}\d{3,4})\b", user_input.upper())
    if flight_match:
        data["flight_id"] = flight_match.group(1)

    # Trích xuất Email
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", user_input)
    if email_match:
        data["passenger_email"] = email_match.group(0)

    # Trích xuất Tên
    name_match = re.search(r"(?:tên(?: là)?|tôi(?: là)?)\s+([A-Za-zÀ-ỹ\s]+)(?:,|\.|-|$|email|và)", user_input.lower())
    if name_match:
        data["passenger_name"] = name_match.group(1).strip().title()

    # Trích xuất xác nhận đồng ý
    if re.search(r"\b(đồng ý|ok|yes|xác nhận|tiến hành|book|đặt đi)\b", user_input, re.IGNORECASE):
        data["confirmed"] = True
        
    return data

def run_plan_execute(user_input: str, current_state: dict = None) -> dict:
    state = current_state or {"history": [], "plan": None, "extracted_data": {}}
    
    # Cập nhật thông tin mới từ người dùng vào state
    state["extracted_data"].update(extract_flight_data(user_input))
    
    if not state.get("plan"):
        state["plan"] = create_plan(user_input)
        
    for step in state["plan"]["steps"]:
        action = step["action"]
        
        if action == "search_flights":
            missing = [field for field in ["from_city", "to_city", "date"] if not state["extracted_data"].get(field)]
            if missing:
                return handoff(reason="Thiếu thông tin chuyến bay (Nơi đi, nơi đến, ngày).", missing_fields=missing, state=state)
            
            args = {
                "from_city": state["extracted_data"]["from_city"], 
                "to_city": state["extracted_data"]["to_city"], 
                "date": str(state["extracted_data"]["date"])  # Ép kiểu an toàn thành string
            }
            try:
                result = search_flights.invoke(args)
            except Exception as e:
                return {"status": "ERROR", "message": str(e)}
                
            state["history"].append({"action": "search_flights", "args": args, "result": result})
            if not result:
                return {"status": "ERROR", "message": "Không tìm thấy chuyến bay phù hợp.", "state": state}
            
            requested_flight_id = state["extracted_data"].get("flight_id")
            if requested_flight_id:
                matched_flight = next((f for f in result if f.get("flight_id") == requested_flight_id), None)
                if not matched_flight:
                    return {"status": "ERROR", "message": f"Không tìm thấy chuyến {requested_flight_id}.", "state": state}
                state["extracted_data"].update(matched_flight)
            else:
                state["extracted_data"].update(result[0])
            continue
            
        elif action == "check_seat":
            flight_id = state["extracted_data"].get("flight_id")
            if not flight_id:
                return handoff(reason="Không xác định được chuyến bay để kiểm tra ghế.", missing_fields=["flight_id"], state=state)
                
            args = {"flight_id": flight_id}
            try:
                result = check_seat.invoke(args)
            except Exception as e:
                return {"status": "ERROR", "message": str(e)}
                
            state["history"].append({"action": "check_seat", "args": args, "result": result})
            if not result.get("success"):
                return {"status": "ERROR", "message": result.get("error"), "state": state}
            if result.get("available_seats", 0) <= 0:
                return {"status": "ERROR", "message": "Chuyến bay đã hết chỗ.", "state": state}
            continue
            
        elif action == "validate_passenger":
            missing = [f for f in ["passenger_name", "passenger_email"] if not state["extracted_data"].get(f)]
            if missing:
                return handoff(reason="Vui lòng cung cấp Tên và Email của bạn để tiến hành đặt vé (VD: Tên là Nguyễn Văn A, email a@gmail.com).", missing_fields=missing, state=state)
                
            try:
                request = FlightRequest(
                    from_city=state["extracted_data"]["from_city"],
                    to_city=state["extracted_data"]["to_city"],
                    date=state["extracted_data"]["date"],
                    passenger_name=state["extracted_data"]["passenger_name"],
                    passenger_email=state["extracted_data"]["passenger_email"],
                    flight_id=state["extracted_data"]["flight_id"],
                    confirmed=state["extracted_data"].get("confirmed", False)
                )
            except Exception as e:
                return {"status": "ERROR", "message": str(e), "state": state}
                
            # Lưu lại vào state (sử dụng mode='json' để ngày tháng được format chuẩn chuỗi ISO)
            state["extracted_data"].update(request.model_dump(mode='json'))
            state["history"].append({"action": "validate_passenger", "result": "VALID"})
            continue

        elif action == "request_confirmation":
            if not state["extracted_data"].get("confirmed"):
                flight = state["extracted_data"].get("flight_id")
                name = state["extracted_data"].get("passenger_name")
                return handoff(reason=f"Thông tin hợp lệ. Bạn {name} có xác nhận đặt chuyến {flight} không? (Trả lời 'Đồng ý' hoặc 'Xác nhận')", missing_fields=["confirmed"], state=state)
            
            state["history"].append({"action": "request_confirmation", "result": "CONFIRMED"})
            continue
            
        elif action == "book_flight":
            if not check_permission("book_flight", state["extracted_data"].get("confirmed", False)):
                return {"status": "ERROR", "message": "Chưa có quyền đặt vé do chưa xác nhận.", "state": state}

            args = {
                "flight_id": state["extracted_data"]["flight_id"],
                "passenger_name": state["extracted_data"]["passenger_name"],
                "passenger_email": state["extracted_data"]["passenger_email"],
                "confirmed": state["extracted_data"]["confirmed"]
            }
            try:
                result = book_flight.invoke(args)
            except Exception as e:
                return {"status": "ERROR", "message": str(e)}
                
            state["history"].append({"action": "book_flight", "args": args, "result": result})
            if check_completion(result):
                msg = f"🎉 Đặt vé thành công cho {args['passenger_name']}! Mã đặt chỗ của bạn là: {result['booking_id']}"
                return {"status": "COMPLETED", "message": msg, "data": result, "state": state}
            return {"status": "ERROR", "message": result.get("error", "Đặt vé thất bại."), "state": state}
            
        elif action == "get_booking":
            booking_id = state["extracted_data"].get("booking_id")
            if not booking_id:
                return handoff(reason="Vui lòng cung cấp mã đặt chỗ cần tra cứu.", missing_fields=["booking_id"], state=state)
                
            args = {"booking_id": booking_id}
            try:
                result = get_booking.invoke(args)
            except Exception as e:
                return {"status": "ERROR", "message": str(e)}
                
            state["history"].append({"action": "get_booking", "args": args, "result": result})
            if result.get("success"):
                return {"status": "COMPLETED", "message": "Đã tìm thấy thông tin đặt vé.", "data": result, "state": state}
            return {"status": "ERROR", "message": result.get("error"), "state": state}
            
    return {"status": "IN_PROGRESS", "message": "Hệ thống đang chờ lệnh tiếp theo.", "state": state}