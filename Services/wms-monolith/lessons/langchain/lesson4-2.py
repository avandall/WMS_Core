import os
import subprocess
import sys
from dotenv import load_dotenv

# --- [OPTION A: AUTO-IMPORT & INSTALLER] ---
def sync_libraries():
    libs = ["langchain-google-genai", "langchain-chroma", "langchain-community", "python-dotenv"]
    for lib in libs:
        try: __import__(lib.replace("-", "_"))
        except ImportError: subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

sync_libraries()
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import LLMChainExtractor, EmbeddingsFilter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# 1. Cấu hình Model & DB (Dùng model bạn đã chỉ định)
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2-preview")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

# 2. THƯ VIỆN CHUẨN: Sử dụng bộ nén tài liệu (Compressor)
# LLMChainExtractor sẽ đọc qua các tài liệu và chỉ giữ lại những đoạn thực sự liên quan
#compressor = LLMChainExtractor.from_llm(llm=llm)
compressor = EmbeddingsFilter(embeddings=embeddings, similarity_threshold=0.7, k=5)

base_retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

# Đây là Retriever đã được nâng cấp với Reranking/Compression
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=base_retriever
)

# 3. RAG Chain
template = """Bạn là Giáo sư AI. Sử dụng ngữ cảnh đã được nén sau để trả lời:
{context}

Câu hỏi: {question}
"""
prompt = ChatPromptTemplate.from_template(template)

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {"context": compression_retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

if __name__ == "__main__":
    # Test với dữ liệu Lilian Weng
    query = "Các kỹ thuật chính trong Task Decomposition là gì?"
    print(f"🚀 Đang chạy Reranking (Library-Native) với dữ liệu Agent...")
    print(rag_chain.invoke(query))