from langchain_core.messages import HumanMessage
from agent import app

if __name__ == "__main__":
    print("=== Demo 2: Coding Task Execution ===")
    print("User Request: 'Calculate the maximum stress of a 10-inch pipe and return a script that prints the result.'")
    
    initial_state = {
        "messages": [HumanMessage(content="Write a python script that calculates the stress on a 10 inch carbon steel pipe with 500 psi internal pressure and prints it. The wall thickness is 0.5 inches.")]
    }
    
    print("\n--- Invoking Agent ---")
    final_state = app.invoke(initial_state)
    
    print("\n--- Final Tool Result ---")
    print(final_state.get("tool_results", "No tool result"))
