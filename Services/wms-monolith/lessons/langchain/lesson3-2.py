import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

# 1. Khởi tạo tài nguyên (Dùng Gemini 2.5)
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2-preview")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

# 2. Bước Query Transformation: Tự tạo 3 câu hỏi khác nhau
query_prompt = ChatPromptTemplate.from_template(
    "Bạn là chuyên gia AI. Hãy tạo ra 3 câu hỏi tương đương (tiếng Việt) cho câu hỏi này: {question}\nTrả lời chỉ gồm các câu hỏi, cách nhau bởi dấu xuống dòng."
)

# Hàm này sẽ lấy 3 câu hỏi và đi tìm kiếm 3 lần, sau đó gộp kết quả lại
def multi_query_fetch(query_text):
    # Gen 3 câu hỏi
    questions_str = (query_prompt | llm | StrOutputParser()).invoke({"question": query_text})
    questions = questions_str.strip().split("\n")
    print(f"🔍 Các câu hỏi biến thể:\n{questions_str}")
    
    # Tìm kiếm tài liệu cho từng câu hỏi
    all_docs = []
    for q in questions:
        all_docs.extend(retriever.invoke(q))
    
    # Loại bỏ tài liệu trùng lặp (Unique)
    unique_contents = list(set([doc.page_content for doc in all_docs]))
    return "\n\n".join(unique_contents)

# 3. RAG Chain hoàn chỉnh
final_prompt = ChatPromptTemplate.from_template("""Dựa vào ngữ cảnh:
{context}

Trả lời câu hỏi: {question}""")

rag_chain = (
    {"context": RunnableLambda(multi_query_fetch), "question": RunnablePassthrough()}
    | final_prompt
    | llm
    | StrOutputParser()
)

# 4. Chạy thử
if __name__ == "__main__":
    res = rag_chain.invoke("Làm sao để tối ưu hóa kho hàng bằng AI?")
    print(f"\nGiáo sư trả lời:\n{res}")