# Google-Drive-Mirror - Mirror/Indexer of Gdrive with FastAPI
# Copyright (C) 2025 kaif-00z
#
# This file is a part of < https://github.com/kaif-00z/Google-Drive-Mirror/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/kaif-00z/Google-Drive-Mirror/blob/main/LICENSE>.

# if you are using this following code then don't forgot to give proper
# credit to t.me/kAiF_00z (github.com/kaif-00z)


from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# Base

class BaseFileFolder(BaseModel):
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., min_length=1, description="Display name")
    mime_type: str = Field(..., description="MIME type")
    size: str = Field(..., description="Human readable size")
    type: Literal["file", "folder"] = Field(..., description="Item type")
    parent_folder_id: Optional[str] = Field(None, description="Parent folder ID")

class FileFoldersListData(BaseFileFolder):
    pass

class FileFolderData(BaseFileFolder):
    pass

class SearchData(BaseFileFolder):
    pass

class FileFoldersListInfo(BaseModel):
    total_files: int = Field(..., ge=0, description="Total number of files")
    total_folders: int = Field(..., ge=0, description="Total number of folders")
    total_files_size: int = Field(..., ge=0, description="Total size in bytes")
    page_token: Optional[str] = Field(None, description="Pagination token")

# Response models

class BaseResponse(BaseModel):
    success: bool = Field(..., description="Operation status")

class FilesFoldersListResponse(BaseResponse):
    data: List[FileFoldersListData]
    additional_info: FileFoldersListInfo

class FileFolderResponse(BaseResponse):
    data: FileFolderData

class SearchResponse(BaseResponse):
    data: List[SearchData]
    additional_info: FileFoldersListInfo

# Error

class FileNotFound(Exception):
    pass