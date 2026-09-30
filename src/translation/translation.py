import os
from google import genai
from google.genai import types

client = genai.Client()


system_instruction = (
    """
    You are an expert SAS programmer and Python data engineer. Translate the
    provided SAS code (DATA steps, PROC SQL, PROC MEANS, etc.) into 
    production-ready Python (primarily using pandas, numpy, or standard libraries).
    Return only the Python code without explanations or exclamations leading or following the code.
    """
)

sas_code_example_input = """
data work.adult_patients;
    set work.patient_records;
    where age >= 18;
    bmi = weight / (height * height) * 703;
run;

proc means data=work.adult_patients noprint;
    class treatment_group;
    var bmi response_score;
    output out=work.summary_stats 
        mean=mean_bmi mean_score 
        std=std_bmi std_score;
run;
"""

prompt = sas_code_example_input

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.2,
    ),
)

print("=== Python Code ===")
print(response.text)
