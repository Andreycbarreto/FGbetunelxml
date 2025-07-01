#!/usr/bin/env python3
"""
Simple test to debug OpenAI API timeout issue
"""
import os
import logging
from openai import OpenAI

logging.basicConfig(level=logging.INFO)

def simple_test():
    """Test basic OpenAI call without vision"""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    try:
        print("Testing basic OpenAI call...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": "Say hello in JSON format."}
            ],
            max_tokens=100,
            timeout=10
        )
        print(f"Success: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"Basic call failed: {e}")
        return False

def test_with_simple_image():
    """Test with a very small image"""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    try:
        # Create a simple base64 encoded 1x1 pixel image
        import base64
        # Simple 1x1 transparent PNG
        simple_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00:\xd2C\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
        base64_img = base64.b64encode(simple_png).decode('utf-8')
        
        print("Testing with simple image...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in one word."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}
                    ]
                }
            ],
            max_tokens=50,
            timeout=10
        )
        print(f"Success: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"Image call failed: {e}")
        return False

if __name__ == "__main__":
    print("=== OpenAI API Debug Test ===")
    
    # Test 1: Basic call
    basic_ok = simple_test()
    
    # Test 2: Simple image
    if basic_ok:
        image_ok = test_with_simple_image()
        
        if image_ok:
            print("Both tests passed - issue may be with specific PDF processing")
        else:
            print("Image processing failed - vision API issue")
    else:
        print("Basic API calls are failing")