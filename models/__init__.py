# Kjeldahl - Mirror/Indexer of Gdrive with FastAPI
# Copyright (C) 2025 kaif-00z
#
# This file is a part of < https://github.com/kaif-00z/Kjeldahl/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/kaif-00z/Kjeldahl/blob/main/LICENSE>.

# if you are using this following code then don't forgot to give proper
# credit to t.me/kAiF_00z (github.com/kaif-00z)

from pydantic import BaseModel
from typing import List

class FileFoldersListData(BaseModel):
    id: str
    name: str
    mime_type: str
    size: str
    parent_folder_id: str
    type: str = "folder" or "file"

class FileFoldersListInfo(BaseModel):
    total_files: int
    total_folders: int
    total_files_size: int
    page_token: str

class FilesFoldersList(BaseModel):
    success: bool
    data: List[FileFoldersListData]
    additional_info: FileFoldersListInfo

class FileFolderData(BaseModel):
    id: str
    name: str
    mime_type: str
    size: str
    type: str = "folder" or "file"

class FileFolderInfo(BaseModel):
    success: bool
    data: FileFolderData

class SearchData(BaseModel):
    id: str
    name: str
    mime_type: str
    size: str
    type: str = "folder" or "file"

class FileFoldersListInfo(BaseModel):
    total_files: int
    total_folders: int
    total_files_size: int
    page_token: str

class SearchList(BaseModel):
    success: bool
    data: List[SearchData]
    additional_info: FileFoldersListInfo