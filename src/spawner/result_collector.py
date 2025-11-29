from dataclasses import asdict, dataclass
import json
import logging
from typing import Any, Callable, TypeAlias
import aio_pika
from dacite import from_dict
from src.spawner.stop_service import stop_solver_controller
from src.utils import solver_director_result_queue_name
from src.database import SessionLocal
from src.config import Config
from src.models import ProjectResult


logger = logging.getLogger(__name__)


async def result_collector():
    solver_director_result_queue = solver_director_result_queue_name()

    logger.info(f"Starting result collector, listening to queue: {solver_director_result_queue}")

    connection = await aio_pika.connect_robust(
        host=Config.RabbitMQ.HOST,
        port=Config.RabbitMQ.PORT,
        login=Config.RabbitMQ.USER,
        password=Config.RabbitMQ.PASSWORD,
    )
    
    async with connection:  
        channel = await connection.channel()
        queue = await channel.declare_queue(solver_director_result_queue, durable=True)        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    db = SessionLocal()
                    try:
                        logger.info("Received result message")
                        result_data = message.body.decode()
                        result_json = json.loads(result_data)
                        if result_json.get("final_message", False):
                            stop_solver_controller(result_json["project_id"])
                            result_json.pop("final_message", None)
                            result_json.pop("total_messages", None)

                        result = ProjectResult.from_json(result_json)
                        
                        db.add(result)
                        db.commit()
                    except Exception as e:
                        db.rollback()
                        logger.error(f"Failed to save result: {e}", exc_info=True)
                        raise
                    finally:
                        db.close()