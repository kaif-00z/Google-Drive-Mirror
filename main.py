# Kjeldahl - Mirror/Indexer of Gdrive with FastAPI
# Copyright (C) 2025 kaif-00z
#
# This file is a part of < https://github.com/kaif-00z/Kjeldahl/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/kaif-00z/Kjeldahl/blob/main/LICENSE>.

# if you are using this following code then don't forgot to give proper
# credit to t.me/kAiF_00z (github.com/kaif-00z)

import logging
import mimetypes
from traceback import format_exc

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.openapi.docs import get_swagger_ui_html

from gdrive import GoogleDriver
from gdrive.errors import FileNotFound

from models import SearchList, FilesFoldersList, FileFolderInfo

log = logging.getLogger(__name__)

app = FastAPI(
    title="Kjeldahl Indexer",
    summary="High Speed Gdrive Mirror, Indexer & File Streamer Written Asynchronous in Python with FastAPI With Awsome Features & Stablility.",
    version="v0.0.1@beta",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", include_in_schema=False)
async def overridden_swagger():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Kjeldahl APIs",
        swagger_favicon_url="https://ssl.gstatic.com/docs/doclist/images/drive_2022q3_32dp.png",
    )

@app.get("/dl/{file_id}", include_in_schema=False)
async def stream_handler(request: Request, file_id: str):
    try:
        return await media_streamer(request, file_id)
    except FileNotFound as e:
        return Response(content=e.reason, status_code=e.resp.status)
    except (AttributeError, ConnectionResetError):
        pass
    except BaseException:
        log.exception(str(format_exc()))
        return Response(content="Something Went Wrong!", status_code=500)


async def media_streamer(request: Request, file_id: str):
    range_header = request.headers.get("Range", 0)
    client = GoogleDriver()
    log.info(
        f"now serving {request.headers.get('X-FORWARDED-FOR')}"
    )

    try:
        file_info = await client.get_file_info(file_id)
    except BaseException as error:
        raise FileNotFound(error)

    file_size = file_info.get("size")

    if range_header:
        from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes = 0
        until_bytes = file_size - 1

    if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        return Response(
            status_code=416,
            content="416: Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    until_bytes = min(until_bytes, file_size - 1)
    req_length = until_bytes - from_bytes + 1

    body = await client.stream_file(file_id)

    mime_type = file_info.get("mimeType")
    file_name = file_info.get("name")
    disposition = "attachment"

    if not mime_type:
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    return StreamingResponse(
        status_code=206 if range_header else 200,
        content=body,
        headers={
            "Content-Type": f"{mime_type}",
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(req_length),
            "Content-Disposition": f'{disposition}; filename="{file_name}"',
            "Accept-Ranges": "bytes",
        },
    )

@app.get("/file/info", response_model=FileFolderInfo)
async def file_info(file_id: str):
    try:
        client = GoogleDriver()
        data = await client.get_file_info(file_id)
        return JSONResponse(
            {
                "success": True,
                "data": data,
            }
        )
    except BaseException as e:
        return JSONResponse(
            {
                "success": False,
                "error": e.reason,
                "data": {}
            },
            status_code=e.resp.status
        )
    
@app.get("/folders/list", response_model=FilesFoldersList)
async def folders_in_root(folder_id: str = None):
    try:
        client = GoogleDriver()
        data, info = await client.list_all() if not folder_id else await client.list_all(folder_id=folder_id)
        return JSONResponse(
            {
                "success": True,
                "data": data,
                "additional_info": info
            }
        )
    except BaseException as e:
        return JSONResponse(
            {
                "success": False,
                "error": e.reason,
                "data": [],
                "additional_info": {}
            },
            status_code=e.resp.status
        )

@app.get("/search", response_model=SearchList)
async def search(query: str):
    try:
        client = GoogleDriver()
        data, info = await client.search_files_in_drive(query)
        return JSONResponse(
            {
                "success": True,
                "data": data,
                "additional_info": info
            }
        )
    except BaseException as e:
        return JSONResponse(
            {
                "success": False,
                "error": e.reason,
                "data": [],
                "additional_info": {}
            },
            status_code=e.resp.status
        )