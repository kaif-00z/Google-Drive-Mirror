# Kjeldahl - Mirror/Indexer of Gdrive with FastAPI
# Copyright (C) 2025 kaif-00z
#
# This file is a part of < https://github.com/kaif-00z/Kjeldahl/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/kaif-00z/Kjeldahl/blob/main/LICENSE>.

# if you are using this following code then don't forgot to give proper
# credit to t.me/kAiF_00z (github.com/kaif-00z)

# inspired from WZML-X, mltb and google-drive-index
# https://github.com/SilentDemonSD/WZML-X/blob/master/bot/helper/mirror_utils/upload_utils/gdriveTools.py under GPLv3 license
# only base (like login & sa management)
# everything else written by me@kaif-00z under AGPLv3 license

from logging import getLogger, ERROR
from pickle import load as pload
from os import path as ospath, listdir
from io import BytesIO
from re import search as re_search
from urllib.parse import parse_qs, urlparse
from random import randrange
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from .utils import (
    hbs,
    run_async,
    asyncio
)
from .config import Var

LOGGER = getLogger(__name__)
getLogger("googleapiclient.discovery").setLevel(ERROR)


class GoogleDriver:
    def __init__(self):
        self.__OAUTH_SCOPE = ["https://www.googleapis.com/auth/drive"]
        self.__G_DRIVE_DIR_MIME_TYPE = "application/vnd.google-apps.folder"
        self.__sa_index = 0
        self.__sa_count = 1
        self.__sa_number = 100
        self.__service = self.__authorize()
        self.cache = []

    def __authorize(self):
        credentials = None
        if Var.IS_SERVICE_ACCOUNT:
            json_files = listdir("accounts")
            self.__sa_number = len(json_files)
            self.__sa_index = randrange(self.__sa_number)
            LOGGER.info(
                f"Authorizing with {json_files[self.__sa_index]} service account"
            )
            credentials = service_account.Credentials.from_service_account_file(
                f"accounts/{json_files[self.__sa_index]}", scopes=self.__OAUTH_SCOPE
            )
        elif ospath.exists("token.pickle"):
            LOGGER.info("Authorize with token.pickle")
            with open("token.pickle", "rb") as f:
                credentials = pload(f)
        else:
            LOGGER.error("token.pickle not found nor service accounts if any!")
        return build("drive", "v3", credentials=credentials, cache_discovery=False)


    def __switchServiceAccount(self):
        if self.__sa_index == self.__sa_number - 1:
            self.__sa_index = 0
        else:
            self.__sa_index += 1
        self.__sa_count += 1
        LOGGER.info(f"Switching to {self.__sa_index} index")
        self.__service = self.__authorize()

    def getIdFromUrl(link):
        if "folders" in link or "file" in link:
            regex = r"https:\/\/drive\.google\.com\/(?:drive(.*?)\/folders\/|file(.*?)?\/d\/)([-\w]+)"
            res = re_search(regex, link)
            if res is None:
                raise IndexError("G-Drive ID not found.")
            return res.group(3)
        parsed = urlparse(link)
        return parse_qs(parsed.query)["id"][0]

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

    @run_async
    def stream_file(
        self,
        file_id_or_link,
        chunk_size=Var.SERVER_SIDE_SPEED * 1024 * 1024,
    ):
        try:
            if "drive.google.com" in file_id_or_link:
                file_id = self.getIdFromUrl(file_id_or_link)
            else:
                file_id = file_id_or_link

            request = self.__service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            )

            buffer = BytesIO()
            downloader = MediaIoBaseDownload(buffer, request, chunksize=chunk_size)

            done = False
            retries = 0
            total_downloaded = 0

            while not done:
                try:
                    status, done = downloader.next_chunk()

                    buffer.seek(0)
                    chunk_data = buffer.read()

                    yield chunk_data

                    buffer.seek(0)
                    buffer.truncate()
                    retries = 0

                except HttpError as err:
                    if err.resp.status in [500, 502, 503, 504] and retries < 10:
                        retries += 1
                        continue

                    if err.resp.get("content-type", "").startswith("application/json"):
                        reason = eval(err.content).get("error").get("errors")[0].get("reason")
                        if reason in ["downloadQuotaExceeded", "dailyLimitExceeded"]:
                            if self.__sa_count < self.__sa_number:
                                self.__switchServiceAccount()
                                LOGGER.info(f"Got {reason}, switching service account...")
                                yield from self.loop.run_until_complete(self.stream_file(file_id_or_link))
                                return
                            else:
                                raise Exception(f"All service accounts quota exceeded: {reason}")
                    raise err

            LOGGER.info(f"Finished streaming: {total_downloaded} bytes")
        except Exception as err:
            LOGGER.error(f"Streaming error: {str(err)}")
            raise err

        
    @run_async
    def get_file_info(self, file_id_or_link) -> dict:
        try:
            if "drive.google.com" in file_id_or_link:
                file_id = self.getIdFromUrl(file_id_or_link)
            else:
                file_id = file_id_or_link
            
            meta = self.__getFileMetadata(file_id)

            return {
                "name": meta["name"],
                "id": meta["id"],
                "mime_type": meta.get("mimeType"),
                "size": hbs(int(meta.get("size", 0))),
                "type": "folder" if meta.get("mimeType") == self.__G_DRIVE_DIR_MIME_TYPE else "file"
            }
        except Exception as err:
            LOGGER.error(f"Error getting file info: {str(err)}")
            raise err

    async def list_all(self, folder_id: str = Var.ROOT_FOLDER_ID, recurse_folders: bool = False, page_token: str = None, page_size: int = 100) -> list:
        all_items = []
        info = {
            "total_files": 0,
            "total_folders": 0,
            "total_files_size": 0
        }

        @run_async
        def _list_folder(current_folder_id: str):
            try:
                response = (
                    self.__service.files()
                    .list(
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        q=f"'{current_folder_id}' in parents and trashed = false",
                        spaces="drive",
                        pageSize=page_size,
                        fields=(
                            "nextPageToken, "
                            "files(id, name, mimeType, size, shortcutDetails)"
                        ),
                        orderBy="folder, name",
                        pageToken=page_token,
                    )
                    .execute()
                )

                for file in response.get("files", []):
                    shortcut = file.get("shortcutDetails")
                    if shortcut:
                        target_id = shortcut.get("targetId")
                        try:
                            file = self.__getFileMetadata(target_id)
                        except HttpError as err:
                            if err.resp.status == 404:
                                LOGGER.warning(f"Shortcut target not found: {target_id}")
                                continue
                            else:
                                raise
                    
                    name = file.get("name")
                    mime_type = file.get("mimeType")
                    size = int(file.get("size", 0))
                    file_id = file.get("id")
                    parent_folder_id = current_folder_id

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
                        "parent_folder_id": parent_folder_id,
                        "type": item_type,
                    })

                    if item_type == "folder":
                        info["total_folders"] += 1
                    else:
                        info["total_files"] += 1
                        info["total_files_size"] += size

                    if item_type == "folder" and recurse_folders:
                        asyncio.run(_list_folder(file_id))

                info["page_token"] = response.get("nextPageToken")
            except HttpError as err:
                if err.resp.status == 404:
                    LOGGER.warning(f"Folder not found: {current_folder_id}")
                    raise err
                LOGGER.error(f"HTTP Error {err.resp.status}: {err}")
                raise err
            except Exception as e:
                LOGGER.error(f"Error listing folder {current_folder_id}: {e}")
                raise err

        await _list_folder(folder_id)

        return all_items, info
    
    @run_async
    def search_files_in_drive(self, query: str, page_token=None, page_size=100) -> list:
        all_items = []
        info = {
            "total_files": 0,
            "total_folders": 0,
            "total_files_size": 0
        }

        query = query.strip().replace("'", "\\'")
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
            response = self.__service.files().list(**params).execute()
            for file in response.get("files", []):
                shortcut = file.get("shortcutDetails")
                if shortcut:
                    target_id = shortcut.get("targetId")
                    try:
                        file = self.__getFileMetadata(target_id)
                    except HttpError as err:
                        if err.resp.status == 404:
                            LOGGER.warning(f"Shortcut target not found: {target_id}")
                            continue
                        else:
                            raise
                
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

            info["page_token"] = response.get("nextPageToken")
        except HttpError as err:
            LOGGER.error(f"HTTP Error {err.resp.status}: {err}")
            raise err
        except Exception as e:
            LOGGER.error(f"Error while searching: {e}")
            raise err
        
        return all_items, info