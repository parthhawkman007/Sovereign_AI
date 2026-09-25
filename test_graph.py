from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agent import AgentState, neuron_node, reasoning_node, coding_node, validation_node, _is_deliverable_request
from langchain_core.messages import HumanMessage

def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("neuron", neuron_node)
    builder.add_node("coding", coding_node)
    builder.add_node("validation", validation_node)
    builder.add_node("reasoning", reasoning_node)

    builder.add_edge(START, "neuron")
    
    def route_neuron(state):
        actions = state.get("next_action", [])
        if "coding" in actions: return "coding"
        return "reasoning"

    builder.add_conditional_edges("neuron", route_neuron, {"coding": "coding", "reasoning": "reasoning"})
    
    def route_coding(state):
        user_msg = state["messages"][-1].content
        # BUG-11 FIX: wrap in HumanMessage list so _is_deliverable_request works correctly
        if _is_deliverable_request([HumanMessage(content=user_msg)]):
            return "validation"
        return "reasoning"
        
    builder.add_conditional_edges("coding", route_coding, {"validation": "validation", "reasoning": "reasoning"})
    builder.add_edge("validation", "reasoning")
    builder.add_edge("reasoning", END)
    
    return builder.compile(checkpointer=MemorySaver())

g = build_graph()
config = {"configurable": {"thread_id": "test_unit"}}
res = g.invoke({"messages": [HumanMessage(content="A three-phase industrial load operates at 415 V, 25 A and PF 0.82. Calculate the power.")]}, config)
print("FINAL:")
print(res["messages"][-1].content)
