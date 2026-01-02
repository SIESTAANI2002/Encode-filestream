import os
import json
from pydrive2.drive import GoogleDrive
from pydrive2.auth import GoogleAuth
from oauth2client.service_account import ServiceAccountCredentials
from bot.core.reporter import rep
from traceback import format_exc
from bot import Var  # ✅ Import from __init__.py

def gdrive_auth():
    try:
        # Load service account info from Var
        sa_info = Var.SERVICE_ACCOUNT_JSON
        if not sa_info:
            raise Exception("❌ SERVICE_ACCOUNT_JSON not found in Var")

        # Fix private key formatting (important for Linux)
        if "\\n" in sa_info.get("private_key", ""):
            sa_info["private_key"] = sa_info["private_key"].replace("\\n", "\n")

        scopes = ['https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_info, scopes)
        
        gauth = GoogleAuth()
        gauth.credentials = creds
        drive = GoogleDrive(gauth)
        return drive

    except Exception as e:
        raise Exception(f"❌ GDrive Auth Failed: {str(e)}")


async def upload_file(file_path, filename, folder_id=None):
    try:
        drive = gdrive_auth()

        if not folder_id:
            folder_id = os.environ.get("DRIVE_FOLDER_ID") or Var.DRIVE_FOLDER_ID
        if not folder_id:
            raise Exception("❌ DRIVE_FOLDER_ID not set in Config Vars")

        file = drive.CreateFile({
            "title": filename,
            "parents": [{"id": folder_id}]
        })
        file.SetContentFile(file_path)
        file.Upload()
        return f"https://drive.google.com/uc?id={file['id']}"

    except Exception as e:
        await rep.report(format_exc(), "error")
        raise e


async def upload_to_drive(file_path, folder_id=None):
    filename = os.path.basename(file_path)
    return await upload_file(file_path, filename, folder_id)
