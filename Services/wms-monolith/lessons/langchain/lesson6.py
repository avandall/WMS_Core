from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langgraph.graph import StateGraph, END
from langchain_core.messages import ChatMessage, HumanMessage, BaseMessage
import os
from dotenv import load_dotenv
from typing import TypedDict, Optional

load_dotenv()

#1. Cấu hình Model & DB
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0, api_key=os.getenv("GROQ_API_KEY"))
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

#2. Dinh nghĩa Graph
class GraphState(TypedDict):
    question: str
    documents: Optional[str]
    generation: str

# 3. Định nghĩa các Nút (Nodes) trong tư duy của AI
def retrieve(state):
    print("--- 🔍 Đang truy xuất dữ liệu từ VectorDB ---")
    question = state["question"]
    docs = retriever.invoke(question)
    return {"documents": [d.page_content for d in docs], "question": question}

def grade_documents(state):
    print("--- ⚖️ Đang thẩm định độ liên quan của tài liệu ---")
    question = state["question"]
    docs = state["documents"]
    
    # Ở bước này, trong thực tế ta dùng LLM để chấm điểm (Sẽ học sâu ở Lesson 8)
    # Tạm thời ta giữ lại toàn bộ để hiểu luồng của Graph
    return {"documents": docs, "question": question}

def generate(state):
    print("--- ✍️ Đang tổng hợp câu trả lời cuối cùng ---")
    question = state["question"]
    docs = state["documents"]
    
    context = "\n\n".join(docs)
    prompt = f"Dựa vào ngữ cảnh: {context}\n\nTrả lời câu hỏi: {question}"
    
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"generation": response.content}

# 4. Xây dựng Workflow (Graph)
workflow = StateGraph(GraphState)

# Thêm các bước vào Graph
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("generate", generate)

# Nối các bước lại với nhau
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade_documents")
workflow.add_edge("grade_documents", "generate")
workflow.add_edge("generate", END)

# Compile Graph
app = workflow.compile()

# 5. Chạy Agent
if __name__ == "__main__":
    inputs = {"question": "Lilian Weng nói gì về Long-term memory?"}
    for output in app.stream(inputs):
        for key, value in output.items():
            print(f"Bước [{key}]: Xong")
    
    print(f"\n🤖 Kết quả cuối cùng:\n{value['generation']}")