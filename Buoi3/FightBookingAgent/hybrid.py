from react_agent import react_agent
from plan_execute import create_plan, extract_flight_data 
from harness import handoff

def run_hybrid(user_input: str, current_state: dict = None) -> dict:
    # Khởi tạo trạng thái bộ nhớ giống plan_execute
    state = current_state or {"history": [], "plan": None, "extracted_data": {}}
    
    # 1. Trích xuất thông tin mới từ người dùng và cập nhật vào state
    state["extracted_data"].update(extract_flight_data(user_input))

    # 2. Lập kế hoạch bằng LLM nếu chưa có
    if not state.get("plan"):
        try:
            state["plan"] = create_plan(user_input)
        except Exception as e:
            return {"status": "ERROR", "message": str(e), "state": state}

    actions = [step["action"] for step in state["plan"]["steps"]]

    # 3. KIỂM TRA ĐIỀU KIỆN (Gatekeeper)
    # Nếu kế hoạch có search_flights -> Kiểm tra nơi đi, nơi đến, ngày
    if "search_flights" in actions:
        missing = [f for f in ["from_city", "to_city", "date"] if not state["extracted_data"].get(f)]
        if missing:
            return handoff(reason="Thiếu thông tin chuyến bay (Nơi đi, nơi đến, ngày).", missing_fields=missing, state=state)

    # Nếu kế hoạch có book_flight -> Kiểm tra Tên và Email
    if "validate_passenger" in actions or "book_flight" in actions:
        missing = [f for f in ["passenger_name", "passenger_email"] if not state["extracted_data"].get(f)]
        if missing:
            return handoff(reason="Vui lòng cung cấp Tên và Email của bạn để tiến hành đặt vé (VD: Tên là Nguyễn Văn A, email a@gmail.com).", missing_fields=missing, state=state)

    # Nếu chưa có xác nhận từ người dùng -> Yêu cầu xác nhận
    if "request_confirmation" in actions or "book_flight" in actions:
        if not state["extracted_data"].get("confirmed"):
            name = state["extracted_data"].get("passenger_name", "bạn")
            flight = state["extracted_data"].get("flight_id", "chuyến bay này")
            return handoff(reason=f"Thông tin đã hợp lệ. {name} có đồng ý đặt {flight} không? (Trả lời 'Đồng ý' hoặc 'Xác nhận')", missing_fields=["confirmed"], state=state)

    
    # Đóng gói dữ liệu để đưa cho ReAct
    plan_str = str(state["plan"])
    data_str = str(state["extracted_data"])

    execution_input = (
        "Thực hiện yêu cầu đặt vé sau theo kế hoạch.\n"
        f"Kế hoạch cần làm: {plan_str}\n"
        f"Dữ liệu đã thu thập: {data_str}\n\n"
        "LƯU Ý QUAN TRỌNG CỦA HỆ THỐNG:\n"
        "- Mọi thông tin đã được kiểm duyệt và người dùng đã đồng ý.\n"
        "- HÃY GỌI TOOLS để thực thi. Sử dụng chính xác Tên và Email từ 'Dữ liệu đã thu thập'.\n"
        "- Truyền thẳng tham số confirmed=True vào tool book_flight.\n"
        "- Trả về kết quả cuối cùng báo cáo thành công và mã đặt chỗ."
    )

    try:
        # Chuyển yêu cầu cùng kế hoạch cho ReAct Executor
        result = react_agent.invoke(
            {
                "messages": [
                    {"role": "user", "content": execution_input}
                ]
            },
            config={"recursion_limit": 15},
        )
        
        return {
            "status": "COMPLETED",
            "message": result["messages"][-1].content,
            "data": state["extracted_data"],
            "state": state
        }
    except Exception as e:
        return {
            "status": "ERROR", 
            "message": f"Lỗi trong quá trình ReAct thực thi: {str(e)}", 
            "state": state
        }