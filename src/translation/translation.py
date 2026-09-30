import os
from google import genai
from google.genai import types

client = genai.Client()


system_instruction = (
    """
    You are an expert SAS programmer and Python data engineer. Translate the
    provided SAS code (DATA steps, PROC SQL, PROC MEANS, etc.) into idiomatic,
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

prompt = f"Translate the following SAS code into Python:\n\n```sas\n{sas_code_example_input}\n```"

# 3. Request the translation
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.2,  # Low temperature for deterministic, structured code
    ),
)

# 4. Output the result
print("=== Generated Python Code ===")
print(response.text)