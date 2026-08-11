import os
import glob
import requests
import time

def upload_resumes(directory_path: str, max_files: int = 15):
    """
    Uploads PDF resumes to the local FastAPI backend.
    """
    api_url = "http://localhost:3005/api/v1/candidates/"
    
    # Find all PDFs in the given directory
    pdf_files = glob.glob(os.path.join(directory_path, "*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {directory_path}")
        return
        
    print(f"Found {len(pdf_files)} resumes. Uploading the first {max_files} to avoid exhausting LLM credits...")
    
    files_to_upload = pdf_files[:max_files]
    success_count = 0
    
    for file_path in files_to_upload:
        filename = os.path.basename(file_path)
        print(f"\nUploading: {filename}...")
        
        try:
            with open(file_path, 'rb') as f:
                # The endpoint expects the file field to be named "file"
                files = {'file': (filename, f, 'application/pdf')}
                
                # Add headers for typical frontend requests (though local bypassing might not need it)
                # The endpoint requires a tenant_id header because of TenantDep in router
                headers = {
                    "x-tenant-id": "default"
                }
                
                response = requests.post(api_url, files=files, headers=headers)
                
                if response.status_code in (200, 201):
                    print(f"SUCCESS! {filename} was parsed and ingested.")
                    success_count += 1
                else:
                    print(f"FAILED to upload {filename}. Status Code: {response.status_code}")
                    print(f"Error Message: {response.text}")
                    
        except Exception as e:
            print(f"Error uploading {filename}: {e}")
            
        # Give a small delay to avoid hitting LLM API rate limits too quickly
        time.sleep(0.5)
        
    print(f"\nFinished! Successfully uploaded {success_count}/{len(files_to_upload)} resumes.")

if __name__ == "__main__":
    resume_dir = "/home/ubuntu/HR_AI/data/data"
    upload_resumes(resume_dir, max_files=2500)
