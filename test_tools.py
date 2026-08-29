from langchain_ollama import ChatOllama
from langchain_core.tools import tool

@tool
def dummy(x: int) -> int:
    '''This is a dummy tool that takes an integer x.'''
    return x

llm = ChatOllama(model='phi4-mini:latest', temperature=0)
llm_with_tools = llm.bind_tools([dummy])
res = llm_with_tools.invoke('Call the dummy tool with the number 42.')
print(res.tool_calls)
