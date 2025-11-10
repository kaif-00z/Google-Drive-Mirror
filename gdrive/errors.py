# Kjeldahl - Mirror/Indexer of Gdrive with FastAPI
# Copyright (C) 2025 kaif-00z
#
# This file is a part of < https://github.com/kaif-00z/Kjeldahl/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/kaif-00z/Kjeldahl/blob/main/LICENSE>.


class FileNotFound(Exception):
    message = "File not found or client is down"