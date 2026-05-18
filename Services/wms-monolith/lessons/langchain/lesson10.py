import os
from typing import Annotated, Literal, TypedDict
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage

from langchain_core.tools import tool
from sqlalchemy import create_all, text
import sqlalchemy

# Định nghĩa Tool để AI tự gọi khi cần tra cứu DB
@tool
def query_inventory_db(sku_code: str):
    """
    Truy vấn số lượng tồn kho thực tế từ Database PostgreSQL dựa trên mã SKU.
    """
    # Thay đổi thông tin kết nối phù hợp với DB của bạn
    engine = sqlalchemy.create_engine("postgresql://user:password@localhost:5432/wms_db")
    
    with engine.connect() as conn:
        query = text("SELECT quantity, location FROM inventory WHERE sku = :sku")
        result = conn.execute(query, {"sku": sku_code}).fetchone()
        
    if result:
        return f"SKU {sku_code} hiện có {result[0]} sản phẩm tại vị trí {result[1]}."
    return f"Không tìm thấy thông tin cho mã SKU {sku_code}."

# 1. Khởi tạo LLM và gắn Tool
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
tools = [query_inventory_db]
llm_with_tools = llm.bind_tools(tools)

# 2. Định nghĩa State
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], lambda x, y: x + y]

# 3. Các Nodes logic
def call_model(state: AgentState):
    print("--- 🧠 NODE: Agent đang suy luận ---")
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}

# ToolNode là node đặc biệt của LangGraph tự động chạy các hàm tool
tool_node = ToolNode(tools)

# 4. Logic rẽ nhánh (Router)
def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return "__end__"

# 5. Xây dựng Graph Giai đoạn 2
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.set_entry_point("agent")

# Agent -> Có cần dùng Tool không? -> Nếu có qua 'tools', nếu không thì END
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent") # Sau khi dùng tool, quay lại agent để tổng hợp câu trả lời

app = workflow.compile()