import os
import subprocess
import sys
from typing import List, TypedDict, Annotated
import operator
from dotenv import load_dotenv

# --- [STAGE 0] AUTO-INSTALLER ---
def sync_libraries():
    libs = ["langchain-groq", "langchain-chroma", "langgraph", "langchain-community", "sentence-transformers", "python-dotenv"]
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

# 1. Cấu hình (Giữ nguyên hệ sinh thái Groq + Local Embeddings)
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# 2. State mới: Thêm phần chứa các thực thể (Entities)
class GraphState(TypedDict):
    question: str
    documents: List[str]
    entities: List[str] # Danh sách các thực thể tìm được
    generation: str

# 3. Nodes tư duy mới
def extract_entities(state):
    print("--- 🧠 Bước 1: Trích xuất thực thể từ câu hỏi ---")
    question = state["question"]
    
    # Dùng LLM để lấy ra các từ khóa quan trọng (Entities)
    prompt = f"Trích xuất các thực thể (danh từ riêng, thuật ngữ kỹ thuật) từ câu hỏi này. Chỉ trả về danh sách, cách nhau dấu phẩy: {question}"
    res = llm.invoke([HumanMessage(content=prompt)])
    entities = [e.strip() for e in res.content.split(",")]
    return {"entities": entities}

def graph_retrieval(state):
    print(f"--- 🕸️ Bước 2: Tìm kiếm kiểu Đồ thị cho các thực thể: {state['entities']} ---")
    # Ở đây chúng ta mô phỏng việc tìm kiếm các đoạn văn bản có chứa các thực thể này
    all_docs = []
    for entity in state["entities"]:
        # Tìm kiếm Vector dựa trên từng thực thể thay vì cả câu hỏi
        docs = retriever.invoke(entity)
        all_docs.extend([d.page_content for d in docs])
    
    # Loại bỏ trùng lặp
    return {"documents": list(set(all_docs))}

def final_generate(state):
    print("--- ✍️ Bước 3: Tổng hợp kiến thức từ Đồ thị và Vector ---")
    context = "\n\n".join(state["documents"])
    prompt = f"Ngữ cảnh: {context}\n\nCâu hỏi: {state['question']}"
    res = llm.invoke([HumanMessage(content=prompt)])
    return {"generation": res.content}

# 4. Xây dựng Workflow
workflow = StateGraph(GraphState)

workflow.add_node("extract_entities", extract_entities)
workflow.add_node("graph_retrieval", graph_retrieval)
workflow.add_node("generate", final_generate)

workflow.set_entry_point("extract_entities")
workflow.add_edge("extract_entities", "graph_retrieval")
workflow.add_edge("graph_retrieval", "generate")
workflow.add_edge("generate", END)

app = workflow.compile()

if __name__ == "__main__":
    inputs = {"question": "Mối liên hệ giữa Planning và Memory trong cấu trúc Agent là gì?"}
    for output in app.stream(inputs):
        for key, value in output.items():
            print(f"[{key}] hoàn tất.")
    
    print(f"\n🤖 Agent phản hồi:\n{value['generation']}")