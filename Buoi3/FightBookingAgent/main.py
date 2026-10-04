import time

from react_agent import run_react
from plan_execute import run_plan_execute
from hybrid import run_hybrid

def main():
    print("=== FLIGHT BOOKING AGENT ===")
    print("1. ReAct")
    print("2. Plan-then-Execute")
    print("3. Hybrid")

    choice = input("Chọn Agent (1/2/3): ").strip()
    if choice not in ["1", "2", "3"]:
        print("Lựa chọn không hợp lệ.")
        return

    current_state = None
    
    user_input = input("Bạn: ")
    start = time.perf_counter()

    while True:
        if choice == "1":
            # Nếu hàm run_react của bạn có hỗ trợ truyền state, hãy thêm current_state vào nhé
            result = run_react(user_input) 
        elif choice == "2":
            # Truyền current_state vào để hệ thống nhớ các bước đã chạy và dữ liệu đã trích xuất
            result = run_plan_execute(user_input, current_state)
        elif choice == "3":
            result = run_hybrid(user_input, current_state)

        if isinstance(result, dict) and "state" in result:
            current_state = result["state"]

        status = result.get("status") if isinstance(result, dict) else "UNKNOWN"

        if status == "NEEDS_USER_INPUT":
            print(f"\nBot: {result.get('reason')}")
            user_input = input("Bạn: ")
            
            continue 

        elif status == "COMPLETED":
            # Đã xong việc, in kết quả và thoát vòng lặp
            print(f"\nBot: {result.get('message')}")
            print("\n=== DỮ LIỆU ĐẶT VÉ ===")
            print(result.get("data"))
            break

        elif status == "ERROR":
            # Có lỗi xảy ra, in lỗi và thoát
            print(f"\nBot (Lỗi): {result.get('message')}")
            break

        elif status == "IN_PROGRESS":
            # Hoàn thành kế hoạch nhưng chưa dứt điểm thành COMPLETED
            print(f"\nBot: {result.get('message')}")
            break

        else:
            # Fallback cho các Agent không trả về cấu trúc dictionary có status (như ReAct nguyên bản)
            print("\n=== KẾT QUẢ ===")
            print(result)
            break

    end = time.perf_counter()
    print(f"\nThời gian thực hiện: {end - start:.2f} giây")

if __name__ == "__main__":
    main()