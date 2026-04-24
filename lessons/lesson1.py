import os
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

# Thiết lập API Key 2026
os.environ["GOOGLE_API_KEY"] = "AIza..." 

# Khởi tạo model mạnh nhất cho RAG hiện tại
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", # Model đời mới, cực nhanh
    temperature=0
)

# Khởi tạo Embedding model (Dùng bản v2 mới nhất)
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2-preview")

print("--- Giáo sư AI: Hệ thống đã sẵn sàng cho bài học số 1! ---")