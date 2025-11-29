# Google-Drive-Mirror - Mirror/Indexer of Gdrive with FastAPI
# Copyright (C) 2025 kaif-00z
#
# This file is a part of < https://github.com/kaif-00z/Google-Drive-Mirror/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/kaif-00z/Google-Drive-Mirror/blob/main/LICENSE>.

# inspired from WZML-X, mltb and google-drive-index
# https://github.com/SilentDemonSD/WZML-X/blob/master/bot/helper/mirror_utils/upload_utils/gdriveTools.py under GPLv3 license
# only base (like login & sa management)
# everything else written by me@kaif-00z under AGPLv3 license

import aiohttp, mimetypes
from logging import getLogger, WARNING
from pickle import load as pload
from os import path as ospath, listdir
from random import randrange
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from urllib.parse import urlencode
import requests

from libs.time_cache import timed_cache

from .utils import (
    hbs,
    run_async,
    asyncio
)
from .config import Var

LOGGER = getLogger(__name__)
getLogger("googleapiclient.discovery").setLevel(WARNING)

class GoogleDriver:
    def __init__(self):
        self.__OAUTH_SCOPE = ["https://www.googleapis.com/auth/drive"]
        self.__G_DRIVE_DIR_MIME_TYPE = "application/vnd.google-apps.folder"
        self.__sa_index = 0
        self.__sa_count = 1
        self.__sa_number = 100
        self.__token = {}
        self.__service = self.__authorize()

    def __authorize(self):
        credentials = None
        if Var.IS_SERVICE_ACCOUNT and (json_files := listdir("accounts")):
            self.__sa_number = len(json_files)
            self.__sa_index = randrange(self.__sa_number)
            LOGGER.info(
                f"Authorizing with {json_files[self.__sa_index]} service account"
            )
            credentials = service_account.Credentials.from_service_account_file(
                f"accounts/{json_files[self.__sa_index]}", scopes=self.__OAUTH_SCOPE
            )
            self.__token[self.__sa_index] = credentials.token
        elif ospath.exists("token.pickle"):
            LOGGER.info("Authorize with token.pickle")
            with open("token.pickle", "rb") as f:
                credentials = pload(f)
                self.__token["pickle"] = self._fetch_access_token(credentials)
        else:
            LOGGER.error("token.pickle not found nor service accounts if any!")
        return build("drive", "v3", credentials=credentials, cache_discovery=False)
    
    def _fetch_access_token(self, credentials):
        url = "https://www.googleapis.com/oauth2/v4/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        # Normal OAuth refresh-token mode
        post_data = {
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
            "grant_type": "refresh_token",
        }

        body = urlencode(post_data)

        # Retry logic (3 attempts)
        response = None
        for i in range(3):
            response = requests.post(url, headers=headers, data=body)
            if response.status_code == 200:
                break

        if response is None:
            raise RuntimeError("Failed to fetch access token") 

        return response.json().get("access_token")
    
    def _get_token(self):
        if Var.IS_SERVICE_ACCOUNT:
            return self.__token.get(self.__sa_index)
        return self.__token.get("pickle")

    @run_async
    def __switchServiceAccount(self):
        if self.__sa_index == self.__sa_number - 1:
            self.__sa_index = 0
        else:
            self.__sa_index += 1
        self.__sa_count += 1
        LOGGER.info(f"Switching to {self.__sa_index} index")
        self.__service = self.__authorize()

    @run_async
    def __getFileMetadata(self, file_id):
        return (
            self.__service.files()
            .get(
                fileId=file_id,
                supportsAllDrives=True,
                fields="name, id, mimeType, size",
            )
            .execute()
        )

    
    async def stream_file(self, file_id: str, file: dict, range_header: int = 0):
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

        file_name = file["name"]
        file_size = file.get("size")
        mime_type = file.get("mime_type")

        headers = {"Authorization": f"Bearer {self._get_token()}"}
        if range_header:
            headers["Range"] = str(range_header)

        res = None
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None))
        for attempt in range(3):
            try:
                res = await session.get(url, headers=headers)
                if res.status in (200, 206):
                    break
            except Exception as err:
                LOGGER.error(str(err))

        if res is None:
            raise HTTPException(500, "Unknown error while contacting Google Drive")

        if res.status == 404:
            raise HTTPException(404, "File Not Found")

        if res.status == 403:
            details = await res.text()
            raise HTTPException(403, details)

        if res.status not in (200, 206):
            details = await res.text()
            raise HTTPException(res.status, details)

        async def stream():
            try:
                async for chunk in res.content.iter_chunked(1024 * 1024):
                    if chunk:
                        yield chunk
            except BaseException as e:
                if isinstance(e, asyncio.CancelledError):
                    LOGGER.warning(f"Client disconnected while streaming file {file_id}")
                else:
                    LOGGER.error(f"Stream error: {e}")
                raise
            finally:
                await session.close()

        response = StreamingResponse(
            content=stream(),
            media_type=mime_type
        )

        response.headers["Content-Disposition"] = f'attachment; filename="{file_name}"'

        if not range_header and file_size:
            response.headers["Content-Length"] = str(file_size)

        if res.status == 206:
            response.status_code = 206
            for h in ["Content-Range", "Accept-Ranges"]:
                if h in res.headers:
                    response.headers[h] = res.headers[h]
        else:
            response.status_code = 200

        return response

    @timed_cache(seconds=600) # 10mins is good for this
    async def get_file_info(self, file_id) -> dict:
        try:
            file_id = file_id.strip()
            
            meta = await self.__getFileMetadata(file_id)

            mime_type = meta.get("mimeType") or mimetypes.guess_type(meta["name"])[0] or "application/octet-stream"

            return {
                "name": meta["name"],
                "id": meta["id"],
                "mime_type": mime_type,
                "size": int(meta.get("size", 0)),
                "type": "folder" if meta.get("mimeType") == self.__G_DRIVE_DIR_MIME_TYPE else "file"
            }
        except Exception as err:
            LOGGER.error(f"Error getting file info: {str(err)}")
            raise err

    @timed_cache(seconds=300) # 5 mins
    async def list_all(self, folder_id: str = Var.ROOT_FOLDER_ID, page_token: str = None, page_size: int = 100):
        all_items = []
        info = {
            "total_files": 0,
            "total_folders": 0,
            "total_files_size": 0,
            "page_token": None
        }

        async def _process_file_batch(files: list):
            tasks = [_process_single_file(file) for file in files]
            await asyncio.gather(*tasks)

        async def _process_single_file(file: dict):
            try:
                name = file.get("name")
                mime_type = file.get("mimeType")
                size = int(file.get("size", 0))
                file_id = file.get("id")
                
                item_type = (
                    "folder"
                    if mime_type == self.__G_DRIVE_DIR_MIME_TYPE
                    else "file"
                )

                item_data = {
                    "id": file_id,
                    "name": name,
                    "mime_type": mime_type,
                    "size": hbs(size),
                    "parent_folder_id": folder_id,
                    "type": item_type,
                }

                if item_type == "folder":
                    info["total_folders"] += 1
                else:
                    info["total_files"] += 1
                    info["total_files_size"] += size

                all_items.append(item_data)
            except Exception as e:
                LOGGER.error(f"Error processing file {file.get('id')}: {e}")
                raise e

        async def _list_folder():
            try:
                response = await _execute_files_list()
                
                files = response.get("files", [])
                if not files:
                    return
                
                # Process files in parallel batches
                batch_size = 50
                for i in range(0, len(files), batch_size):
                    batch = files[i:i + batch_size]
                    await _process_file_batch(batch)    

                info["page_token"] = response.get("nextPageToken")
                
            except HttpError as err:
                if err.resp.status == 404:
                    LOGGER.warning(f"Folder not found: {folder_id}")
                else:
                    LOGGER.error(f"HTTP Error {err.resp.status}: {err}")
                raise err
            except Exception as e:
                LOGGER.error(f"Error listing folder {folder_id}: {e}")
                raise e

        @run_async
        def _execute_files_list():
            try:
                return self.__service.files().list(
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    q=f"'{folder_id}' in parents AND trashed = false AND mimeType != 'application/vnd.google-apps.shortcut' ",
                    spaces="drive",
                    pageSize=page_size,
                    fields=(
                        "nextPageToken, "
                        "files(id, name, mimeType, size)"
                    ),
                    orderBy="folder, name",
                    pageToken=page_token,
                ).execute()
            except Exception as err:
                raise err

        await _list_folder()
        return all_items, info

    @timed_cache(seconds=300) # 5mins
    async def search_files_in_drive(self, query: str, page_token=None, page_size=100):
        all_items = []
        info = {
            "total_files": 0,
            "total_folders": 0,
            "total_files_size": 0,
            "page_token": None
        }
        query = query.strip().replace("'", "\\'")

        @run_async
        def _execute_search():
            if not query:
                return all_items, info

            words = query.split()
            name_cond = " AND ".join([f"name contains '{w}'" for w in words])

            params = {
                "q": (
                    "trashed = false "
                    "AND mimeType != 'application/vnd.google-apps.shortcut' "
                    "AND mimeType != 'application/vnd.google-apps.document' "
                    "AND mimeType != 'application/vnd.google-apps.spreadsheet' "
                    "AND mimeType != 'application/vnd.google-apps.form' "
                    "AND mimeType != 'application/vnd.google-apps.site' "
                    "AND name != '.password' "
                    f"AND ({name_cond})"
                ),
                "fields": "nextPageToken, files(id, driveId, name, mimeType, size, modifiedTime)",
                "pageSize": page_size,
                "orderBy": "folder, name, modifiedTime desc",
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True
            }

            params["corpora"] = "allDrives"

            if page_token:
                params["pageToken"] = page_token

            try:
                return self.__service.files().list(**params).execute()
            except Exception as err:
                raise err
        
        async def _process_file_batch(files: list):
            tasks = [_process_single_file(file) for file in files]
            await asyncio.gather(*tasks)

        async def _process_single_file(file: dict):
            try:
                name = file.get("name")
                mime_type = file.get("mimeType")
                size = int(file.get("size", 0))
                file_id = file.get("id")

                item_type = (
                    "folder"
                    if mime_type == self.__G_DRIVE_DIR_MIME_TYPE
                    else "file"
                )

                all_items.append({
                    "id": file_id,
                    "name": name,
                    "mime_type": mime_type,
                    "size": hbs(size),
                    "type": item_type,
                })

                if item_type == "folder":
                    info["total_folders"] += 1
                else:
                    info["total_files"] += 1
                    info["total_files_size"] += size
            except Exception as e:
                LOGGER.error(f"Error processing file {file.get('id')}: {e}")
                raise e

        async def _list_():
            try:
                response = await _execute_search()
                
                files = response.get("files", [])
                if not files:
                    return
                
                # Process files in parallel batches
                batch_size = 50
                for i in range(0, len(files), batch_size):
                    batch = files[i:i + batch_size]
                    await _process_file_batch(batch)    

                info["page_token"] = response.get("nextPageToken")
            except HttpError as err:
                LOGGER.error(f"HTTP Error {err.resp.status}: {err}")
                raise err
            except Exception as e:
                LOGGER.error(f"Error while searching: {e}")
                raise e
        
        await _list_()
        return all_items, info


# to get new driver instance in every 30mins
@timed_cache(seconds=1800)
def get_drive_client() -> GoogleDriver:
    return GoogleDriver()

t = GoogleDriver()