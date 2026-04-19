import google.generativeai as genai

# Masukkan API Key baru Anda di sini
genai.configure(api_key="AIzaSyAilqp4-qeUYABEZwhinCFBHbcKBAwIhOI")

print("Daftar model yang bisa Anda gunakan:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"- {m.name}")