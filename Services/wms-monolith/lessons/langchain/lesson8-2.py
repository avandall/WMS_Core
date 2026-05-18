import os
from typing import List, TypedDict, Literal
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

load_dotenv()

# 1. Cấu hình Model & DB
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# 2. Cấu hình State (Thêm biến attempts)
class GraphState(TypedDict):
    question: str
    documents: List[str]
    is_relevant: str
    generation: str
    attempts: int  # Biến đếm số lần đã thử transform

# --- 3. ĐỊNH NGHĨA CÁC NODES ---

def retrieve_node(state):
    print(f"--- 📥 NODE 1: Truy xuất (Lần {state.get('attempts', 0) + 1}) ---")
    docs = retriever.invoke(state["question"])
    return {"documents": [d.page_content for d in docs]}

def grade_node(state):
    print("--- ⚖️ NODE 2: Thẩm định chất lượng ---")
    question = state["question"]
    docs = state["documents"]
    
    if not docs:
        return {"is_relevant": "no"}

    grader_prompt = f"""Bạn là giám thị. Đánh giá xem đoạn văn sau có chứa thông tin để trả lời câu hỏi không.
    Trả lời 'yes' hoặc 'no'.
    Câu hỏi: {question}
    Đoạn văn: {docs[0]}"""
    
    res = llm.invoke([HumanMessage(content=grader_prompt)])
    score = res.content.lower().strip()
    return {"is_relevant": "yes" if "yes" in score else "no"}

def transform_query_node(state):
    print("--- 🔄 NODE 3: Đang tối ưu lại câu hỏi bằng AI ---")
    question = state["question"]
    attempts = state.get("attempts", 0) + 1
    
    # Logic thực tế cho Node 3: Dùng LLM để viết lại câu hỏi tốt hơn
    transform_prompt = f"""Bạn là chuyên gia tối ưu câu lệnh. Câu hỏi sau đây không tìm thấy kết quả trong database.
    Hãy viết lại câu hỏi này sao cho rõ ràng và dễ tìm kiếm hơn, nhưng vẫn giữ nguyên ý định ban đầu.
    Câu hỏi cũ: {question}
    Câu hỏi mới (chỉ trả về câu hỏi):"""
    
    res = llm.invoke([HumanMessage(content=transform_prompt)])
    new_question = res.content.strip()
    print(f"    👉 Câu hỏi mới: {new_question}")
    
    return {"question": new_question, "attempts": attempts}

def generate_node(state):
    print("--- ✍️ NODE 4: Tổng hợp câu trả lời ---")
    context = "\n\n".join(state["documents"])
    prompt = f"Dựa vào: {context}\n\nTrả lời: {state['question']}"
    res = llm.invoke([HumanMessage(content=prompt)])
    return {"generation": res.content}

def fallback_node(state):
    print("--- ❌ NODE 5: Từ chối sau nhiều lần thử ---")
    return {"generation": "Sau khi thử tìm kiếm lại, tôi vẫn không thấy dữ liệu tin cậy. Vui lòng cung cấp thêm chi tiết."}

# --- 4. XÂY DỰNG GRAPH CÓ ĐIỀU KIỆN ---

workflow = StateGraph(GraphState)

workflow.add_node("retrieve", retrieve_node)
workflow.add_node("grade", grade_node)
workflow.add_node("transform_query", transform_query_node)
workflow.add_node("generate", generate_node)
workflow.add_node("fallback", fallback_node)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade")

# Logic rẽ nhánh quan trọng nhất
def decide_next_step(state) -> Literal["generate", "transform_query", "fallback"]:
    if state["is_relevant"] == "yes":
        return "generate"
    
    # Nếu chưa thử lần nào (attempts=0), cho phép transform_query
    if state.get("attempts", 0) < 1:
        return "transform_query"
    
    # Nếu đã thử rồi mà vẫn 'no', đi đến fallback
    return "fallback"

workflow.add_conditional_edges(
    "grade",
    decide_next_step,
    {
        "generate": "generate",
        "transform_query": "transform_query",
        "fallback": "fallback"
    }
)

workflow.add_edge("transform_query", "retrieve") # Quay lại vòng lặp
workflow.add_edge("generate", END)
workflow.add_edge("fallback", END)

app = workflow.compile()

if __name__ == "__main__":
    # Chạy thử với câu hỏi khó để kích hoạt vòng lặp
    inputs = {"question": "MIPS trong Agent là gì?", "attempts": 0}
    result = app.invoke(inputs)
    print(f"\n🤖 Kết quả cuối cùng:\n{result['generation']}")