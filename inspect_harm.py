
import google.generativeai as genai
from google.generativeai.types import HarmCategory

print("HarmCategory members:")
for member in HarmCategory:
    print(f"{member.name} = {member.value}")
