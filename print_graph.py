import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ai.graphs.hiring_graph import build_hiring_graph

def main():
    graph = build_hiring_graph()
    # Get mermaid diagram
    mermaid_code = graph.get_graph().draw_mermaid()
    print(mermaid_code)

if __name__ == "__main__":
    main()
