import os
import subprocess
import sys
from dotenv import load_dotenv

# --- [STAGE 0] AUTO-IMPORT & INSTALLER ---
def sync_libraries():
    # Cài đặt langchain-groq và sentence-transformers để chạy embedding cục bộ
    libs = [
        "langchain-groq", 
        "langchain-chroma", 
        "langchain-community", 
        "langchain-classic",
        "sentence-transformers", 
        "rank-bm25", 
        "python-dotenv"
    ]
    for lib in libs:
        try:
            __import__(lib.replace("-", "_"))
        except ImportError:
            print(f"📦 Đang cài đặt {lib}...")
            subprocess.call([sys.executable, "-m", "pip", "install", lib])

sync_libraries()
load_dotenv()

from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

# 1. Cấu hình Model
# Dùng Llama-3.1-8b-instant theo yêu cầu của bạn
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0, api_key=os.getenv("GROQ_API_KEY"))

# Dùng model embedding miễn phí, chạy cục bộ trên máy bạn
# 'all-MiniLM-L6-v2' là model cực nhẹ, phù hợp cho việc học tập
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Kết nối database (Hãy đảm bảo bạn đã xóa folder chroma_db cũ nếu trước đó dùng Gemini)
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

# 2. Thiết lập BM25 Retriever (Keyword Search)
# Lấy dữ liệu từ blog Lilian Weng đã index để làm keyword source
try:
    all_data = vectorstore.get()
    docs_for_bm25 = [
        Document(page_content=txt, metadata=meta) 
        for txt, meta in zip(all_data['documents'], all_data['metadatas'])
    ]
    bm25_retriever = BM25Retriever.from_documents(docs_for_bm25)
    bm25_retriever.k = 3
except Exception as e:
    print(f"⚠️ Lưu ý: DB trống hoặc lỗi. Bạn cần chạy lại file Indexing với HuggingFaceEmbeddings trước. Lỗi: {e}")
    bm25_retriever = None

# 3. Thiết lập Vector Retriever (Semantic Search)
vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# 4. Hybrid Search (Kết hợp bằng EnsembleRetriever)
if bm25_retriever:
    hybrid_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[0.4, 0.6] # 40% keyword, 60% semantic
    )
else:
    hybrid_retriever = vector_retriever

# 5. RAG Chain
prompt = ChatPromptTemplate.from_template("""
Bạn là Giáo sư AI 2026. Hãy sử dụng ngữ cảnh sau để trả lời câu hỏi.
Ngữ cảnh:
{context}

Câu hỏi: {question}
""")

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {"context": hybrid_retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

if __name__ == "__main__":
    # Test với dữ liệu Lilian Weng
    query = "Quy trình Chain of Thought (CoT) hoạt động như thế nào trong Agent?"
    print(f"🚀 Truy vấn Hybrid (Llama-3.1-8b + Local Embeddings)...")
    print(rag_chain.invoke(query))