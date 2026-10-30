"""Explicit manual live-provider diagnostic; never runs during pytest collection."""

def main():
    import os
    import base64
    import google.generativeai as genai
    from dotenv import load_dotenv
    
    # Load environment variables from .env file in project root
    load_dotenv('../.env')
    
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-2.5-flash-image-preview')
    
    with open('../Dream_Layer_Resources/output/DreamLayer_BFL_00031_.png', 'rb') as img_file:
        img_data = base64.b64encode(img_file.read()).decode()
    
    prompt = "make the car black."
    response = model.generate_content([{'inline_data': {'mime_type': 'image/png', 'data': img_data}}, prompt])
    
    # Debug: Print response structure
    print("Response structure:")
    for i, candidate in enumerate(response.candidates):
        print(f"Candidate {i}:")
        for j, part in enumerate(candidate.content.parts):
            print(f"  Part {j}: {type(part).__name__}")
            if hasattr(part, 'inline_data'):
                print(f"    Has inline_data: {hasattr(part.inline_data, 'data')}")
                if hasattr(part.inline_data, 'data'):
                    print(f"    Data size: {len(part.inline_data.data)} bytes")
    
    # Find and extract image data
    generated_img = None
    for candidate in response.candidates:
        for part in candidate.content.parts:
            if hasattr(part, 'inline_data') and hasattr(part.inline_data, 'data'):
                generated_img = part.inline_data.data  # Already binary, no base64 decode needed
                break
        if generated_img:
            break
    
    if generated_img:
        with open('edited_nano_banana.png', 'wb') as out:
            out.write(generated_img)
        print(f"Image saved: {len(generated_img)} bytes")
    else:
        print("No image data found in response!")


if __name__ == "__main__":
    main()
