import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()  # Tải biến môi trường từ file .env nếu có

# 1. Cấu hình Key (Dùng Groq để tránh tốn token Google)
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY") # Vẫn cần để load Embedding từ DB

# 2. Kết nối tới "Thư viện" đã tạo ở Lesson 2
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2-preview")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

# Thiết lập Retriever (Lấy ra 3 đoạn văn bản liên quan nhất)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# 3. Khởi tạo "Bộ não" Groq - Model Llama 3.3 70B (Rất thông minh)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0
)

# 4. Tạo mẫu câu hỏi (Prompt) chuẩn RAG
template = """Bạn là một giáo sư AI. Hãy trả lời câu hỏi dựa trên ngữ cảnh được cung cấp dưới đây. 
Nếu không có trong ngữ cảnh, hãy nói là bạn không biết, đừng tự bịa ra thông tin.

Ngữ cảnh:
{context}

Câu hỏi: {question}
"""
prompt = ChatPromptTemplate.from_template(template)

# 5. Xây dựng luồng xử lý (Chain)
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 6. Chạy thử nghiệm
print("--- Hệ thống RAG (Gemini + Groq) đang trả lời... ---")
query = "Task decomposition là gì?"
response = rag_chain.invoke(query)
print(f"\nKết quả:\n{response}")