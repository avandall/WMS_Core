import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

load_dotenv()

# 1. Khởi tạo
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2-preview")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5}) # Lấy top 5 đoạn

# 2. Logic Reranking bằng Gemini 2.5
rerank_prompt = ChatPromptTemplate.from_template("""
Bạn là một chuyên gia thẩm định dữ liệu. 
Dựa vào câu hỏi của người dùng, hãy chọn ra duy nhất 3 đoạn văn bản liên quan nhất từ danh sách dưới đây.
Sắp xếp chúng theo độ liên quan giảm dần.

Câu hỏi: {question}

Danh sách tài liệu:
{docs}

Chỉ trả ra nội dung các đoạn văn bản được chọn, ngăn cách bằng dấu '---'.
""")

def rerank_logic(input_data):
    question = input_data["question"]
    docs = input_data["docs"]
    
    # Chuyển list docs thành string để gửi cho Gemini
    docs_str = "\n\n".join([f"Đoạn {i+1}: {d.page_content}" for i, d in enumerate(docs)])
    
    # Dùng Gemini để lọc và sắp xếp lại
    reranked_content = (rerank_prompt | llm | StrOutputParser()).invoke({
        "question": question, 
        "docs": docs_str
    })
    return reranked_content

# 3. RAG Chain với Reranking
rag_chain = (
    {
        "docs": retriever, 
        "question": RunnablePassthrough()
    }
    | RunnableLambda(lambda x: {
        "context": rerank_logic(x),
        "question": x["question"]
    })
    | ChatPromptTemplate.from_template("Sử dụng ngữ cảnh sau để trả lời: {context}\n\nCâu hỏi: {question}")
    | llm
    | StrOutputParser()
)

# 4. Chạy thử nghiệm
if __name__ == "__main__":
    query = "Các kỹ thuật chính trong Task Decomposition là gì?"
    print(f"--- Đang thực hiện RAG + Reranking cho: {query} ---")
    print(rag_chain.invoke(query))