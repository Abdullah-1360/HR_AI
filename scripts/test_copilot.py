import requests
import json

res = requests.post("http://localhost:3005/api/v1/copilot/chat", json={"query": "oracle developer"})
print("Status:", res.status_code)
data = res.json()
print("Retrieved count:", len(data.get("retrieved_candidates", [])))
print("Answer snippet:", data.get("answer", "")[:300])
