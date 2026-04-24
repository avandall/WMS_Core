import os
import subprocess
import sys
from typing import List, TypedDict, Literal
from dotenv import load_dotenv

# --- [STAGE 0] AUTO-INSTALLER ---
def sync_libraries():
    libs = ["langchain-groq", "langchain-chroma", "langgraph", "langchain-community", "sentence-transformers"]
    for lib in libs:
        try: __import__(lib.replace("-", "_"))
        except ImportError: subprocess.call([sys.executable, "-m", "pip", "install", lib])

sync_libraries()
load_dotenv()

from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

# 1. Khởi tạo (Llama-3.1-8b trên Groq)
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# 2. Định nghĩa State (Sổ ghi chép)
class GraphState(TypedDict):
    question: str
    documents: List[str]
    is_relevant: str # "yes" hoặc "no"
    generation: str

# --- 3. ĐỊNH NGHĨA 5 NODES BIẾN THỂ ---

def retrieve_node(state):
    print("--- 📥 NODE 1: Truy xuất dữ liệu ---")
    docs = retriever.invoke(state["question"])
    return {"documents": [d.page_content for d in docs]}

def grade_node(state):
    print("--- ⚖️ NODE 2: Thẩm định chất lượng (Grader) ---")
    question = state["question"]
    docs = state["documents"]
    
    # Prompt yêu cầu LLM chấm điểm "yes" hoặc "no"
    grader_prompt = f"""Bạn là giám thị. Hãy đánh giá xem đoạn văn sau có chứa câu trả lời cho câu hỏi không. 
    Chỉ trả lời đúng 1 từ: 'yes' hoặc 'no'.
    Câu hỏi: {question}
    Đoạn văn: {docs[0] if docs else "Trống"}"""
    
    res = llm.invoke([HumanMessage(content=grader_prompt)])
    score = res.content.lower().strip()
    
    return {"is_relevant": "yes" if "yes" in score else "no"}

def transform_query_node(state):
    print("--- 🔄 NODE 3: Tài liệu rác! Đang tối ưu lại câu hỏi ---")
    # Nếu dữ liệu không tốt, ta thử viết lại câu hỏi để tìm kiếm lại (hoặc kết thúc)
    return {"question": f"Giải thích chi tiết về: {state['question']}"}

def generate_node(state):
    print("--- ✍️ NODE 4: Tổng hợp câu trả lời ---")
    context = "\n\n".join(state["documents"])
    prompt = f"Dựa vào: {context}\n\nHỏi: {state['question']}"
    res = llm.invoke([HumanMessage(content=prompt)])
    return {"generation": res.content}

def fallback_node(state):
    print("--- ❌ NODE 5: Từ chối trả lời ---")
    return {"generation": "Xin lỗi, tôi không tìm thấy thông tin tin cậy trong tài liệu để trả lời câu này."}

# --- 4. XÂY DỰNG GRAPH ĐA NHÁNH ---

workflow = StateGraph(GraphState)

workflow.add_node("retrieve", retrieve_node)
workflow.add_node("grade", grade_node)
workflow.add_node("transform_query", transform_query_node)
workflow.add_node("generate", generate_node)
workflow.add_node("fallback", fallback_node)

# Thiết lập luồng chạy
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade")

# ĐÂY LÀ ĐIỂM QUAN TRỌNG: Rẽ nhánh dựa trên kết quả của Node Grade
def decide_to_generate(state) -> Literal["generate", "fallback"]:
    if state["is_relevant"] == "yes":
        return "generate"
    else:
        return "fallback"

workflow.add_conditional_edges(
    "grade",
    decide_to_generate,
    {
        "generate": "generate",
        "fallback": "fallback"
    }
)

workflow.add_edge("generate", END)
workflow.add_edge("fallback", END)

app = workflow.compile()

if __name__ == "__main__":
    # Test 1: Câu hỏi có trong tài liệu
    print("\n--- TEST 1: Câu hỏi đúng trọng tâm ---")
    inputs1 = {"question": "Lilian Weng nói gì về Chain of Thought?"}
    print(app.invoke(inputs1)["generation"])

    # Test 2: Câu hỏi không liên quan (Rác)
    print("\n--- TEST 2: Câu hỏi lạc đề ---")
    inputs2 = {"question": "Làm thế nào để nấu phở bò?"}
    print(app.invoke(inputs2)["generation"])