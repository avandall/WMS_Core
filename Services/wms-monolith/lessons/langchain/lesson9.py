import os
import json
from typing import List, TypedDict, Literal
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

load_dotenv()

# 1. Models: Dùng 8b để chạy nhanh, 70b để chấm điểm cho chuẩn
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
evaluator_llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# 2. State mở rộng cho cả 2 Lesson
class GraphState(TypedDict):
    question: str
    documents: List[str]
    generation: str
    eval_score: float
    eval_critique: str

# --- 3. CÁC NODES HỢP THỂ ---

def retrieve_node(state):
    print("--- 📥 [L8] Truy xuất dữ liệu ---")
    docs = retriever.invoke(state["question"])
    return {"documents": [d.page_content for d in docs]}

def generate_node(state):
    print("--- ✍️ [L8] Đang tạo câu trả lời tạm thời ---")
    context = "\n\n".join(state["documents"])
    prompt = f"Ngữ cảnh: {context}\n\nHỏi: {state['question']}\n\nTrả lời ngắn gọn:"
    res = llm.invoke([HumanMessage(content=prompt)])
    return {"generation": res.content}

def evaluate_node(state):
    print("--- ⚖️ [L9] Đang thẩm định câu trả lời vừa tạo ---")
    eval_prompt = f"""Bạn là chuyên gia thẩm định. So sánh câu trả lời với ngữ cảnh.
    Ngữ cảnh: {state['documents']}
    Câu trả lời: {state['generation']}
    
    Nếu câu trả lời có thông tin không nằm trong ngữ cảnh (bịa đặt), hãy cho điểm thấp.
    Chỉ trả về JSON: {{"score": <0-10>, "critique": "<nhận xét>"}}"""
    
    res = evaluator_llm.invoke([HumanMessage(content=eval_prompt)])
    try:
        data = json.loads(res.content)
    except:
        data = {"score": 0, "critique": "Lỗi định dạng đánh giá."}
    
    return {"eval_score": data["score"], "eval_critique": data["critique"]}

def fallback_node(state):
    print(f"--- ❌ [L9 Result] Điểm quá thấp ({state['eval_score']}). Từ chối! ---")
    return {"generation": f"Tôi không thể trả lời vì dữ liệu không đủ độ tin cậy. (Lý do: {state['eval_critique']})"}

# --- 4. XÂY DỰNG WORKFLOW KẾT NỐI ---

workflow = StateGraph(GraphState)

workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)
workflow.add_node("evaluate", evaluate_node) # Lesson 9 cắm vào đây
workflow.add_node("fallback", fallback_node)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", "evaluate")

# Rẽ nhánh dựa trên điểm số của Lesson 9
def check_quality(state) -> Literal["accept", "reject"]:
    if state["eval_score"] >= 7:
        print(f"✅ Câu trả lời đạt chuẩn ({state['eval_score']}/10)")
        return "accept"
    return "reject"

workflow.add_conditional_edges(
    "evaluate",
    check_quality,
    {
        "accept": END,
        "reject": "fallback"
    }
)
workflow.add_edge("fallback", END)

app = workflow.compile()

if __name__ == "__main__":
    # Test: Một câu hỏi mà dữ liệu trong blog Agent của Lilian Weng không có
    inputs = {"question": "Quy trình đóng gói hàng hóa tại kho của Lilian Weng?"}
    result = app.invoke(inputs)
    print(f"\n🤖 FINAL OUTPUT:\n{result['generation']}")