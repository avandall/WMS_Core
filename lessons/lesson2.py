import os
import bs4
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_community.document_loaders import WebBaseLoader
from langchain_chroma import Chroma
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
import time

load_dotenv()  # Tải biến môi trường từ file .env nếu có


# 1. Cấu hình (Sử dụng Key Gemini 2.5 của bạn)
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")  # Lấy key từ biến môi trường

# Khởi tạo Embedding model bản 2026
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# 2. Load dữ liệu thực tế (Lấy bài blog về Agent của Lilian Weng làm mẫu)
loader = WebBaseLoader(
    web_paths=("https://lilianweng.github.io/posts/2023-06-23-agent/",),
    bs_kwargs=dict(
        parse_only=bs4.SoupStrainer(
            class_=("post-content", "post-title", "post-header")
        )
    ),
)
docs = loader.load()

# 3. Kỹ thuật Semantic Chunking (Điểm mới 2026)
# Nó sẽ tự động tìm điểm ngắt dựa trên độ dốc (gradient) của ý nghĩa văn bản
# text_splitter = SemanticChunker(embeddings)
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000, 
    chunk_overlap=200,
    add_start_index=True
)
semantic_splits = text_splitter.split_documents(docs)

print(f"Đã chia thành {len(semantic_splits)} đoạn dựa trên ngữ nghĩa.")

# 4. Lưu vào Vector Database (Chroma phiên bản mới nhất)
# Lưu ý: Chế độ 'persistent' giúp bạn không phải index lại mỗi lần chạy code
vectorstore = Chroma(embedding_function=embeddings, persist_directory="./chroma_db")

for i in range(0, len(semantic_splits), 100):
    batch = semantic_splits[i : i + 100]
    vectorstore.add_documents(documents=batch)
    time.sleep(1)  # Tạm dừng để tránh quá tải API
print("--- Hệ thống Indexing đã hoàn tất và lưu trữ cục bộ! ---")