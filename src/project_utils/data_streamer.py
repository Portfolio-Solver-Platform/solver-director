

import json
from uuid import UUID

from src.config import Config


async def data_streamer(pool, project_id):
    yield "["

    is_first_item = True
    chunk_size = int(Config.SOLUTION_RETRIEVAL_CHUNK_SIZE)

    async with pool.acquire() as conn:
        async with conn.transaction():
            async for chunk in conn.cursor(
                "SELECT * FROM project_results WHERE project_id = $1 ORDER BY id ASC",
                project_id,
                prefetch=chunk_size
            ):

                for row in chunk:
                    if not is_first_item:
                        yield ", "
                    else:
                        is_first_item = False

                    row_dict = dict(row)
                    if 'project_id' in row_dict and isinstance(row_dict['project_id'], UUID):
                        row_dict['project_id'] = str(row_dict['project_id'])

                    yield row_dict

    yield "]"